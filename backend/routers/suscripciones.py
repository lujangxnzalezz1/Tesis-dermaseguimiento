import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import obtener_usuario_actual
from core.tiempo import ahora
from models.suscripcion import (
    Comprobante, HistorialSuscripcion, Notificacion, Pago, Plan, Suscripcion,
)
from models.usuario import Usuario
from schemas.comunes import limpiar_texto
from services import auditoria_service as audit
from services import suscripcion_service as svc
from services.comprobante_pdf import generar_pdf
from services.exportacion import respuesta_csv

router = APIRouter(tags=["Suscripciones y pagos"])


def plan_a_dict(p: Plan) -> dict:
    return {
        "codigo": p.codigo, "nombre": p.nombre, "precio": str(p.precio), "moneda": p.moneda,
        "periodicidad": p.periodicidad, "duracion_dias": p.duracion_dias,
        "funcionalidades": json.loads(p.funcionalidades), "limites": json.loads(p.limites),
        "condiciones": p.condiciones, "incluye_procesamiento": p.incluye_procesamiento,
    }


@router.get("/planes")
def listar_planes(db: Session = Depends(get_db)):
    """RF-18: catálogo PÚBLICO de planes (sin autenticación). Lo que se muestra sale de la tabla de planes,
    la misma que usa el sistema para aplicar las reglas, así que no puede contradecirlas."""
    planes = db.query(Plan).filter(Plan.activo.is_(True)).order_by(Plan.orden).all()
    return {"planes": [plan_a_dict(p) for p in planes], "dias_de_prueba": settings.TRIAL_DAYS}


def _estado_a_dict(db: Session, usuario: Usuario) -> dict:
    susc = svc.asegurar_suscripcion(db, usuario)
    plan = db.get(Plan, susc.plan_id)
    siguiente = db.get(Plan, susc.plan_siguiente_id) if susc.plan_siguiente_id else None
    pendiente = db.query(Pago).filter(Pago.suscripcion_id == susc.id, Pago.estado == "pendiente").count() > 0
    return {
        "estado": susc.estado, "categoria": svc.clasificar(susc, pendiente), "es_prueba": susc.es_prueba,
        "plan": plan_a_dict(plan), "fecha_inicio": susc.fecha_inicio, "fecha_vencimiento": susc.fecha_vencimiento,
        "dias_restantes": svc.dias_restantes(susc), "cancelada_en": susc.cancelada_en,
        "plan_siguiente": plan_a_dict(siguiente) if siguiente else None,
        "funciones_avanzadas": svc.tiene_acceso_avanzado(db, usuario), "pago_pendiente": pendiente,
    }


@router.get("/suscripcion")
def mi_suscripcion(db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    return _estado_a_dict(db, usuario)


@router.get("/suscripcion/historial")
def historial_suscripcion(db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    susc = svc.asegurar_suscripcion(db, usuario)
    filas = db.query(HistorialSuscripcion).filter(HistorialSuscripcion.suscripcion_id == susc.id).order_by(HistorialSuscripcion.id.desc()).all()
    return [{"fecha": h.fecha, "evento": h.evento, "plan_anterior_id": h.plan_anterior_id, "plan_nuevo_id": h.plan_nuevo_id, "detalle": h.detalle} for h in filas]


class SolicitudCheckout(BaseModel):
    plan_codigo: str = Field(min_length=2, max_length=50)


@router.post("/suscripcion/checkout")
def iniciar_checkout(datos: SolicitudCheckout, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    """Contratar, renovar o cambiar de plan. Si corresponde pagar, devuelve la URL de la pasarela."""
    resultado = svc.iniciar_cambio_o_pago(db, usuario, datos.plan_codigo)
    audit.registrar(db, request, usuario, "suscripciones", "checkout", entidad="plan", entidad_id=datos.plan_codigo,
                    despues={k: v for k, v in resultado.items() if k != "url_pago"})
    return resultado


class SolicitudCancelar(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)
    confirmar: bool = False

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, v):
        return limpiar_texto(v, campo="motivo", max_len=300, obligatorio=True)


@router.post("/suscripcion/cancelar")
def cancelar(datos: SolicitudCancelar, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá la cancelación para continuar. Vas a conservar tus funciones hasta la fecha de vencimiento.")
    antes = _estado_a_dict(db, usuario)
    susc = svc.cancelar_suscripcion(db, usuario, datos.motivo)
    audit.registrar(db, request, usuario, "suscripciones", "cancelar", entidad="suscripcion", entidad_id=susc.id,
                    antes={"estado": antes["estado"]}, despues={"estado": susc.estado}, detalle=datos.motivo)
    return {"mensaje": "Cancelamos tu suscripción. Conservás las funciones Premium hasta el final del período pagado.",
            "fecha_vencimiento": susc.fecha_vencimiento}


@router.get("/pagos/{pago_id}")
def estado_pago(pago_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    pago = db.query(Pago).filter(Pago.id == pago_id, Pago.usuario_id == usuario.id).first()
    if not pago:
        raise HTTPException(404, "No encontramos ese pago.")
    comp = db.query(Comprobante).filter(Comprobante.pago_id == pago.id).first()
    return {"id": pago.id, "estado": pago.estado, "monto": str(pago.monto), "moneda": pago.moneda,
            "referencia": pago.referencia_externa, "comprobante_id": comp.id if comp else None}


def _consulta_pagos(db, usuario, estado, desde, hasta):
    q = db.query(Pago).filter(Pago.usuario_id == usuario.id)
    if estado:
        q = q.filter(Pago.estado == estado)
    if desde:
        q = q.filter(Pago.creado_en >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.filter(Pago.creado_en < datetime.combine(hasta, datetime.min.time()) + timedelta(days=1))
    return q


def _pago_a_dict(db, p: Pago) -> dict:
    comp = db.query(Comprobante).filter(Comprobante.pago_id == p.id).first()
    plan = db.get(Plan, p.plan_id)
    return {"id": p.id, "fecha": p.creado_en, "plan": plan.nombre if plan else "", "tipo": p.tipo, "monto": str(p.monto),
            "moneda": p.moneda, "estado": p.estado, "referencia": p.referencia_externa,
            "comprobante_id": comp.id if comp else None, "comprobante_numero": comp.numero if comp else None}


@router.get("/pagos")
def mis_pagos(
    estado: Optional[str] = Query(None, pattern="^(pendiente|aprobado|rechazado|cancelado)$"),
    desde: Optional[date] = None, hasta: Optional[date] = None,
    pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual),
):
    q = _consulta_pagos(db, usuario, estado, desde, hasta)
    total = q.count()
    filas = q.order_by(Pago.id.desc()).offset((pagina - 1) * tamano).limit(tamano).all()
    return {"items": [_pago_a_dict(db, p) for p in filas], "total": total, "pagina": pagina, "tamano": tamano}


@router.get("/pagos.csv")
def exportar_pagos(
    request: Request, estado: Optional[str] = Query(None, pattern="^(pendiente|aprobado|rechazado|cancelado)$"),
    desde: Optional[date] = None, hasta: Optional[date] = None, decimal: str = Query("coma", pattern="^(coma|punto)$"),
    db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual),
):
    filas = _consulta_pagos(db, usuario, estado, desde, hasta).order_by(Pago.id).all()
    total_aprobado = sum(Decimal(p.monto) for p in filas if p.estado == "aprobado")
    audit.registrar(db, request, usuario, "pagos", "exportar_csv")
    return respuesta_csv(
        "Historial de pagos", ["Fecha", "Referencia", "Tipo", "Estado", "Monto", "Moneda"],
        [(p.creado_en, p.referencia_externa, p.tipo, p.estado, Decimal(p.monto), p.moneda) for p in filas],
        filtros={"estado": estado, "desde": desde, "hasta": hasta, "separador_decimal": decimal},
        totales={"Total aprobado": total_aprobado}, decimal=decimal, prefijo_archivo="pagos",
    )


def _comp_dict(c: Comprobante) -> dict:
    return {
        "id": c.id, "numero": c.numero, "fecha_emision": c.fecha_emision, "estado": c.estado, "emisor": c.emisor_nombre,
        "emisor_ruc": c.emisor_ruc, "pagador": c.pagador_nombre, "pagador_email": c.pagador_email, "concepto": c.concepto,
        "referencia": c.referencia, "periodo": c.periodo, "monto": str(c.monto), "moneda": c.moneda,
        "monto_letras": c.monto_letras, "forma_pago": c.forma_pago, "leyenda": c.leyenda,
        "anulado_en": c.anulado_en, "motivo_anulacion": c.motivo_anulacion,
    }


def _comprobante_propio(db, usuario, comp_id) -> Comprobante:
    c = db.query(Comprobante).filter(Comprobante.id == comp_id, Comprobante.usuario_id == usuario.id).first()
    if not c:
        raise HTTPException(404, "No encontramos ese comprobante.")
    return c


@router.get("/comprobantes")
def mis_comprobantes(
    pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual),
):
    q = db.query(Comprobante).filter(Comprobante.usuario_id == usuario.id)
    return {"items": [_comp_dict(c) for c in q.order_by(Comprobante.id.desc()).offset((pagina - 1) * tamano).limit(tamano).all()],
            "total": q.count(), "pagina": pagina, "tamano": tamano}


@router.get("/comprobantes/{comp_id}")
def ver_comprobante(comp_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    return _comp_dict(_comprobante_propio(db, usuario, comp_id))


@router.get("/comprobantes/{comp_id}/pdf")
def descargar_comprobante(comp_id: int, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    c = _comprobante_propio(db, usuario, comp_id)
    c.reimpresiones += 1
    reimpreso = c.reimpresiones > 1
    if reimpreso and c.estado == "emitido":
        c.estado = "reimpreso"
    db.commit()
    audit.registrar(db, request, usuario, "comprobantes", "reimprimir" if reimpreso else "imprimir", entidad="comprobante", entidad_id=c.id)
    return Response(generar_pdf(c, reimpreso), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{c.numero}.pdf"'})


@router.get("/notificaciones")
def mis_notificaciones(db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    """Genera (si corresponde) los avisos de vencimiento y devuelve los últimos."""
    svc.generar_avisos(db, usuario)
    filas = db.query(Notificacion).filter(Notificacion.usuario_id == usuario.id).order_by(Notificacion.id.desc()).limit(30).all()
    return {"no_leidas": sum(1 for n in filas if not n.leida),
            "items": [{"id": n.id, "tipo": n.tipo, "mensaje": n.mensaje, "fecha": n.fecha, "leida": n.leida} for n in filas]}


@router.post("/notificaciones/{nid}/leida")
def marcar_leida(nid: int, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    n = db.query(Notificacion).filter(Notificacion.id == nid, Notificacion.usuario_id == usuario.id).first()
    if not n:
        raise HTTPException(404, "No encontramos esa notificación.")
    n.leida = True
    db.commit()
    return {"ok": True}
