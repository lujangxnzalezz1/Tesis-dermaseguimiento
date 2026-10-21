import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import obtener_usuario_actual
from core.tiempo import ahora
from core.url_base import url_base
from models.suscripcion import (
    Comprobante, HistorialSuscripcion, Notificacion, Pago, Plan, Suscripcion,
)

ESTADOS_PAGO_FILTRO = "^(pendiente|aprobado|rechazado|cancelado|vencido)$"
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
    nombres = {p.id: p.nombre for p in db.query(Plan).all()}
    return [{"fecha": h.fecha, "evento": h.evento, "plan_anterior_id": h.plan_anterior_id, "plan_nuevo_id": h.plan_nuevo_id,
             "plan_anterior": nombres.get(h.plan_anterior_id), "plan_nuevo": nombres.get(h.plan_nuevo_id), "detalle": h.detalle}
            for h in filas]


class SolicitudCheckout(BaseModel):
    plan_codigo: str = Field(min_length=2, max_length=50)
    # Opcionales, solo para el recibo (el perfil del usuario no guarda RUC ni teléfono)
    documento: Optional[str] = Field(None, max_length=20)
    telefono: Optional[str] = Field(None, max_length=25)

    @field_validator("documento")
    @classmethod
    def _documento(cls, v):
        v = limpiar_texto(v, campo="RUC o CI", max_len=20)
        if v and not re.fullmatch(r"[0-9]{3,12}(-[0-9])?", v.replace(".", "")):
            raise ValueError("El RUC o CI solo puede tener números y, si es RUC, el dígito verificador (por ejemplo 1234567-8).")
        return v.replace(".", "") if v else None

    @field_validator("telefono")
    @classmethod
    def _telefono(cls, v):
        v = limpiar_texto(v, campo="teléfono", max_len=25)
        if v and not re.fullmatch(r"\+?[0-9 ()-]{6,24}", v):
            raise ValueError("El teléfono solo puede tener números, espacios, guiones y el signo + al inicio.")
        return v


@router.get("/suscripcion/cotizacion")
def cotizar(plan_codigo: str = Query(min_length=2, max_length=50), db: Session = Depends(get_db),
            usuario: Usuario = Depends(obtener_usuario_actual)):
    """Importe a pagar y crédito proporcional ANTES de ir a la pasarela (no crea ningún pago)."""
    return svc.cotizar(db, usuario, plan_codigo)


@router.post("/suscripcion/checkout")
def iniciar_checkout(datos: SolicitudCheckout, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    """Contratar, renovar o cambiar de plan. Si corresponde pagar, devuelve la URL de la pasarela."""
    resultado = svc.iniciar_cambio_o_pago(db, usuario, datos.plan_codigo, datos.documento, datos.telefono)
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
    pago = svc.verificar_pago_externo(db, pago)  # 503 controlado si la pasarela no responde
    comp = svc.comprobante_vigente(db, pago.id)
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
    comp = svc.comprobante_vigente(db, p.id)
    plan = db.get(Plan, p.plan_id)
    return {"id": p.id, "fecha": p.creado_en, "plan": plan.nombre if plan else "", "tipo": p.tipo, "monto": str(p.monto),
            "moneda": p.moneda, "estado": p.estado, "referencia": p.referencia_externa,
            "comprobante_id": comp.id if comp else None, "comprobante_numero": comp.numero if comp else None}


@router.get("/pagos")
def mis_pagos(
    estado: Optional[str] = Query(None, pattern=ESTADOS_PAGO_FILTRO),
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
    request: Request, estado: Optional[str] = Query(None, pattern=ESTADOS_PAGO_FILTRO),
    desde: Optional[date] = None, hasta: Optional[date] = None, decimal: str = Query("coma", pattern="^(coma|punto)$"),
    db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual),
):
    filas = _consulta_pagos(db, usuario, estado, desde, hasta).order_by(Pago.id).all()
    # El guaraní no tiene centavos: se exporta como entero
    importe = lambda p: int(p.monto) if p.moneda == "PYG" else Decimal(p.monto)  # noqa: E731
    total_aprobado = sum(importe(p) for p in filas if p.estado == "aprobado")
    audit.registrar(db, request, usuario, "pagos", "exportar_csv")
    return respuesta_csv(
        "Historial de pagos", ["Fecha", "Referencia", "Tipo", "Estado", "Monto", "Moneda"],
        [(p.creado_en, p.referencia_externa, p.tipo, p.estado, importe(p), p.moneda) for p in filas],
        filtros={"estado": estado, "desde": desde, "hasta": hasta, "separador_decimal": decimal},
        totales={"Total aprobado": total_aprobado}, decimal=decimal, prefijo_archivo="pagos",
    )


def _comp_dict(c: Comprobante) -> dict:
    return {
        "id": c.id, "numero": c.numero, "fecha_emision": c.fecha_emision, "estado": c.estado, "emisor": c.emisor_nombre,
        "emisor_ruc": c.emisor_ruc, "pagador": c.pagador_nombre, "pagador_email": c.pagador_email,
        "pagador_documento": c.pagador_documento, "pagador_telefono": c.pagador_telefono, "concepto": c.concepto,
        "referencia": c.referencia, "periodo": c.periodo, "monto": str(c.monto), "moneda": c.moneda,
        "subtotal": str(c.subtotal) if c.subtotal is not None else None, "credito": str(c.credito) if c.credito is not None else None,
        "iva": str(c.iva) if c.iva is not None else None,
        "monto_letras": c.monto_letras, "forma_pago": c.forma_pago, "leyenda": c.leyenda,
        "anulado_en": c.anulado_en, "motivo_anulacion": c.motivo_anulacion,
        "reimpresiones": c.reimpresiones, "reimpreso_en": c.reimpreso_en,
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
    return _entregar_pdf(db, request, usuario, _comprobante_propio(db, usuario, comp_id))


def _entregar_pdf(db: Session, request: Request, usuario: Usuario, c: Comprobante, adjunto: bool = True) -> Response:
    reimpreso = svc.registrar_impresion(db, c)  # el estado sigue «emitido»: solo se cuentan las reimpresiones
    audit.registrar(db, request, usuario, "comprobantes", "reimprimir" if reimpreso else "imprimir", entidad="comprobante", entidad_id=c.id)
    disposicion = "attachment" if adjunto else "inline"
    return Response(generar_pdf(c, reimpreso), media_type="application/pdf",
                    headers={"Content-Disposition": f'{disposicion}; filename="{c.numero}.pdf"'})


USO_ENLACE_PDF = "comprobante_pdf"


@router.post("/comprobantes/{comp_id}/enlace")
def enlace_comprobante(comp_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    """App nativa: el navegador del sistema no puede enviar el token de sesión, así que se entrega un
    enlace firmado que vale solo para ESTE comprobante y por pocos minutos."""
    c = _comprobante_propio(db, usuario, comp_id)
    expira = ahora() + timedelta(minutes=settings.COMPROBANTE_ENLACE_MINUTOS)
    token = jwt.encode({"sub": str(usuario.id), "comp": c.id, "uso": USO_ENLACE_PDF, "exp": expira},
                       settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"url": f"{url_base()}/comprobantes/descarga/{token}", "expira_en": expira}


@router.get("/comprobantes/descarga/{token}")
def descargar_con_enlace(token: str, request: Request, db: Session = Depends(get_db)):
    try:
        datos = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(401, "El enlace de descarga no es válido o venció. Volvé a pedirlo desde la app.")
    if datos.get("uso") != USO_ENLACE_PDF:
        raise HTTPException(401, "El enlace de descarga no es válido o venció. Volvé a pedirlo desde la app.")
    usuario = db.get(Usuario, int(datos.get("sub") or 0))
    if usuario is None or not usuario.activo:
        raise HTTPException(401, "El enlace de descarga no es válido o venció. Volvé a pedirlo desde la app.")
    return _entregar_pdf(db, request, usuario, _comprobante_propio(db, usuario, int(datos.get("comp") or 0)), adjunto=False)


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
