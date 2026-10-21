from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import and_, case, exists, func, or_
from sqlalchemy.orm import Session

from core.config import settings
from core.crypto import cifrar
from core.database import get_db
from core.security import requiere_rol, revocar_sesiones_de_usuario
from core.tiempo import ahora
from models.auditoria import Auditoria
from models.configuracion import ConfiguracionCorreo, PlantillaCorreo, RespuestaSUS
from models.paciente import Paciente
from models.suscripcion import (
    EST_CANCELADA, EST_VENCIDA, PAGO_PENDIENTE, Comprobante, Pago, Plan, Suscripcion,
)
from models.usuario import ROL_ADMIN, ROLES, Usuario
from routers import pacientes as pacientes_router
from schemas.comunes import limpiar_texto
from schemas.paciente import PacienteReactivar
from schemas.usuario import CambioEstadoUsuario, UsuarioAdminRespuesta
from services import auditoria_service as audit
from services import email_service
from services import suscripcion_service as svc
from services.exportacion import respuesta_csv

router = APIRouter(prefix="/admin", tags=["Administración"])
solo_admin = requiere_rol(ROL_ADMIN)
CAMPOS_USUARIO = ["email", "nombre", "rol", "activo", "motivo_inactivacion"]


# ----------------------------------------------------------------- usuarios (RF-05)

@router.get("/usuarios")
def listar_usuarios(
    q: Optional[str] = Query(None, max_length=80), activo: Optional[bool] = None,
    rol: Optional[str] = Query(None, pattern="^(admin|dermatologo)$"),
    pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    consulta = db.query(Usuario)
    if q:
        consulta = consulta.filter(or_(Usuario.email.ilike(f"%{q}%"), Usuario.nombre.ilike(f"%{q}%")))
    if activo is not None:
        consulta = consulta.filter(Usuario.activo.is_(activo))
    if rol:
        consulta = consulta.filter(Usuario.rol == rol)
    total = consulta.count()
    filas = consulta.order_by(Usuario.id).offset((pagina - 1) * tamano).limit(tamano).all()
    return {"items": [UsuarioAdminRespuesta.model_validate(u) for u in filas], "total": total, "pagina": pagina, "tamano": tamano}


def _usuario_objetivo(db, uid) -> Usuario:
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "No encontramos a ese usuario.")
    return u


@router.post("/usuarios/{uid}/inactivar")
def inactivar_usuario(uid: int, datos: CambioEstadoUsuario, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá la inactivación para continuar. El usuario no podrá iniciar sesión.")
    if not datos.motivo:
        raise HTTPException(400, "Indicá el motivo de la inactivación.")
    u = _usuario_objetivo(db, uid)
    if u.id == admin.id:
        raise HTTPException(400, "No podés inactivar tu propia cuenta.")
    if not u.activo:
        raise HTTPException(409, "Ese usuario ya está inactivo.")
    antes = audit.instantanea(u, CAMPOS_USUARIO)
    u.activo = False
    u.fecha_inactivacion = ahora()
    u.fecha_modificacion = ahora()
    u.motivo_inactivacion = datos.motivo
    revocar_sesiones_de_usuario(db, u.id)  # se le cierran las sesiones abiertas
    db.commit()
    audit.registrar(db, request, admin, "usuarios", "inactivar", entidad="usuario", entidad_id=u.id, antes=antes,
                    despues=audit.instantanea(u, CAMPOS_USUARIO), detalle=datos.motivo)
    return {"mensaje": "Usuario inactivado. Se cerraron sus sesiones abiertas."}


@router.post("/usuarios/{uid}/reactivar")
def reactivar_usuario(uid: int, datos: CambioEstadoUsuario, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá la reactivación para continuar.")
    u = _usuario_objetivo(db, uid)
    if u.activo:
        raise HTTPException(409, "Ese usuario ya está activo.")
    antes = audit.instantanea(u, CAMPOS_USUARIO)
    u.activo = True
    u.fecha_reactivacion = ahora()
    u.fecha_modificacion = ahora()
    u.motivo_inactivacion = None
    u.intentos_fallidos, u.bloqueado_hasta = 0, None
    db.commit()
    audit.registrar(db, request, admin, "usuarios", "reactivar", entidad="usuario", entidad_id=u.id, antes=antes,
                    despues=audit.instantanea(u, CAMPOS_USUARIO), detalle=datos.motivo)
    return {"mensaje": "Usuario reactivado."}


class CambioRol(BaseModel):
    rol: str
    confirmar: bool = False

    @field_validator("rol")
    @classmethod
    def _rol(cls, v):
        if v not in ROLES:
            raise ValueError("El rol debe ser admin o dermatologo.")
        return v


@router.put("/usuarios/{uid}/rol")
def cambiar_rol(uid: int, datos: CambioRol, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá el cambio de rol para continuar.")
    u = _usuario_objetivo(db, uid)
    if u.id == admin.id:
        raise HTTPException(400, "No podés cambiar tu propio rol.")
    antes = audit.instantanea(u, CAMPOS_USUARIO)
    u.rol = datos.rol
    u.fecha_modificacion = ahora()
    revocar_sesiones_de_usuario(db, u.id)
    db.commit()
    audit.registrar(db, request, admin, "usuarios", "cambiar_rol", entidad="usuario", entidad_id=u.id, antes=antes, despues=audit.instantanea(u, CAMPOS_USUARIO))
    return {"mensaje": "Rol actualizado. El usuario deberá iniciar sesión de nuevo."}


# ----------------------------------------------------------------- suscripciones (pantalla administrativa)

CATEGORIAS = ("activa", "proxima_a_vencer", "vencida", "cancelada", "pendiente_pago")


def _expresion_categoria():
    """La misma regla que `svc.clasificar`, pero en SQL: así se filtra, cuenta y pagina en la base
    (antes se traían todas las suscripciones y se consultaba un pago pendiente por cada una)."""
    hay_pendiente = exists().where(and_(Pago.suscripcion_id == Suscripcion.id, Pago.estado == PAGO_PENDIENTE))
    limite = ahora() + timedelta(days=max(settings.avisos_dias or [7]))
    return case(
        (Suscripcion.estado == EST_CANCELADA, "cancelada"),
        (and_(Suscripcion.estado == EST_VENCIDA, hay_pendiente), "pendiente_pago"),
        (Suscripcion.estado == EST_VENCIDA, "vencida"),
        (and_(Suscripcion.fecha_vencimiento.isnot(None), Suscripcion.fecha_vencimiento <= limite), "proxima_a_vencer"),
        else_="activa",
    )


def _sincronizar_vencidas(db: Session) -> None:
    """Aplica los vencimientos pendientes solo a las suscripciones que ya pasaron su fecha (normalmente pocas)."""
    for susc in (db.query(Suscripcion)
                 .filter(Suscripcion.estado.in_(svc.ESTADOS_CON_ACCESO), Suscripcion.fecha_vencimiento.isnot(None),
                         Suscripcion.fecha_vencimiento <= ahora())
                 .all()):
        svc.sincronizar(db, susc)


@router.get("/suscripciones")
def listar_suscripciones(
    categoria: Optional[str] = Query(None, pattern="^(activa|proxima_a_vencer|vencida|cancelada|pendiente_pago)$"),
    q: Optional[str] = Query(None, max_length=80), pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    _sincronizar_vencidas(db)
    expr = _expresion_categoria()
    base = db.query(Suscripcion, Usuario, Plan, expr.label("categoria")).join(Usuario, Usuario.id == Suscripcion.usuario_id).join(Plan, Plan.id == Suscripcion.plan_id)
    if q:
        base = base.filter(or_(Usuario.email.ilike(f"%{q}%"), Usuario.nombre.ilike(f"%{q}%")))
    # Resumen por categoría (sobre la búsqueda, sin el filtro de categoría) con un GROUP BY
    sub = base.subquery()
    resumen = {c: 0 for c in CATEGORIAS}
    for c, n in db.query(sub.c.categoria, func.count()).group_by(sub.c.categoria).all():
        resumen[c] = n
    if categoria:
        base = base.filter(expr == categoria)
    total = resumen[categoria] if categoria else sum(resumen.values())
    filas = base.order_by(Suscripcion.id).offset((pagina - 1) * tamano).limit(tamano).all()
    items = [{"suscripcion_id": susc.id, "usuario": usuario.nombre, "email": usuario.email, "plan": plan.nombre,
              "estado": susc.estado, "categoria": c, "fecha_vencimiento": susc.fecha_vencimiento,
              "dias_restantes": svc.dias_restantes(susc), "es_prueba": susc.es_prueba}
             for susc, usuario, plan, c in filas]
    return {"items": items, "total": total, "pagina": pagina, "tamano": tamano, "resumen": resumen}


# ----------------------------------------------------------------- comprobantes

@router.get("/comprobantes")
def listar_comprobantes(
    q: Optional[str] = Query(None, max_length=80, description="Número, nombre o correo del pagador"),
    estado: Optional[str] = Query(None, pattern="^(emitido|anulado|reimpreso)$"),
    pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    consulta = db.query(Comprobante)
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.filter(or_(Comprobante.numero.ilike(patron), Comprobante.pagador_nombre.ilike(patron),
                                       Comprobante.pagador_email.ilike(patron)))
    if estado:
        consulta = consulta.filter(Comprobante.estado == estado)
    total = consulta.count()
    filas = consulta.order_by(Comprobante.id.desc()).offset((pagina - 1) * tamano).limit(tamano).all()
    return {"items": [{"id": c.id, "numero": c.numero, "fecha_emision": c.fecha_emision, "estado": c.estado,
                       "pagador_nombre": c.pagador_nombre, "pagador_email": c.pagador_email, "concepto": c.concepto,
                       "monto": str(c.monto), "moneda": c.moneda, "anulado_en": c.anulado_en, "motivo_anulacion": c.motivo_anulacion}
                      for c in filas],
            "total": total, "pagina": pagina, "tamano": tamano}


class Anulacion(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)
    confirmar: bool = False

    @field_validator("motivo")
    @classmethod
    def _m(cls, v):
        return limpiar_texto(v, campo="motivo", max_len=300, obligatorio=True)


@router.post("/comprobantes/{cid}/anular")
def anular_comprobante(cid: int, datos: Anulacion, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    """Los recibos no se editan: se anulan (queda constancia) y, si corresponde, se emite otro."""
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá la anulación del comprobante para continuar.")
    c = db.get(Comprobante, cid)
    if not c:
        raise HTTPException(404, "No encontramos ese comprobante.")
    if c.estado == "anulado":
        raise HTTPException(409, "Ese comprobante ya estaba anulado.")
    c.estado, c.anulado_en, c.anulado_por, c.motivo_anulacion = "anulado", ahora(), admin.id, datos.motivo
    db.commit()
    audit.registrar(db, request, admin, "comprobantes", "anular", entidad="comprobante", entidad_id=c.id, detalle=datos.motivo)
    return {"mensaje": f"El comprobante {c.numero} fue anulado."}


# ----------------------------------------------------------------- pacientes dados de baja

@router.get("/pacientes-baja")
def listar_pacientes_baja(
    q: Optional[str] = Query(None, max_length=80, description="Cédula, nombre o apellido"),
    pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    """Solo los datos necesarios para identificar la ficha a recuperar (no se exponen datos clínicos)."""
    consulta = (db.query(Paciente, Usuario.email).join(Usuario, Usuario.id == Paciente.dermatologo_id)
                .filter(Paciente.activo.is_(False)))
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.filter(or_(Paciente.cedula.ilike(patron), Paciente.nombre.ilike(patron), Paciente.apellido.ilike(patron)))
    total = consulta.count()
    filas = consulta.order_by(Paciente.eliminado_en.desc(), Paciente.id.desc()).offset((pagina - 1) * tamano).limit(tamano).all()
    return {"items": [{"id": p.id, "cedula": p.cedula, "nombre": p.nombre, "apellido": p.apellido, "dermatologo": email,
                       "eliminado_en": p.eliminado_en, "motivo_eliminacion": p.motivo_eliminacion} for p, email in filas],
            "total": total, "pagina": pagina, "tamano": tamano}


@router.post("/pacientes/{paciente_id}/reactivar")
def reactivar_paciente(paciente_id: int, datos: PacienteReactivar, request: Request, db: Session = Depends(get_db),
                       admin: Usuario = Depends(solo_admin)):
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá la reactivación del paciente para continuar.")
    p = db.get(Paciente, paciente_id)
    if not p:
        raise HTTPException(404, "No encontramos a ese paciente.")
    pacientes_router.reactivar(db, request, admin, p, datos.motivo)
    return {"mensaje": f"El paciente {p.nombre} {p.apellido} volvió a la lista de su dermatólogo."}


@router.post("/recordatorios/ejecutar")
def ejecutar_recordatorios(request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    """Genera avisos de vencimiento para todos los usuarios activos (también disponible como script para cron)."""
    total = 0
    for u in db.query(Usuario).filter(Usuario.activo.is_(True)).all():
        total += len(svc.generar_avisos(db, u))
    audit.registrar(db, request, admin, "suscripciones", "recordatorios", detalle=f"{total} avisos generados")
    return {"avisos_generados": total}


# ----------------------------------------------------------------- auditoría (solo lectura)

def _consulta_auditoria(db, email, modulo, accion, resultado, desde, hasta):
    q = db.query(Auditoria)
    if email:
        q = q.filter(Auditoria.usuario_email.ilike(f"%{email}%"))
    if modulo:
        q = q.filter(Auditoria.modulo == modulo)
    if accion:
        q = q.filter(Auditoria.accion == accion)
    if resultado:
        q = q.filter(Auditoria.resultado == resultado)
    if desde:
        q = q.filter(Auditoria.fecha >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.filter(Auditoria.fecha < datetime.combine(hasta, datetime.min.time()) + timedelta(days=1))
    return q.order_by(Auditoria.id.desc())


def _fila_auditoria(a: Auditoria) -> dict:
    return {"id": a.id, "fecha": a.fecha, "usuario_id": a.usuario_id, "usuario": a.usuario_email, "ip": a.ip, "modulo": a.modulo,
            "accion": a.accion, "entidad": a.entidad, "entidad_id": a.entidad_id, "datos_antes": a.datos_antes,
            "datos_despues": a.datos_despues, "resultado": a.resultado, "detalle": a.detalle}


@router.get("/auditoria")
def ver_auditoria(
    usuario: Optional[str] = None, modulo: Optional[str] = None, accion: Optional[str] = None,
    resultado: Optional[str] = Query(None, pattern="^(exito|fallo)$"), desde: Optional[date] = None, hasta: Optional[date] = None,
    pagina: int = Query(1, ge=1), tamano: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    q = _consulta_auditoria(db, usuario, modulo, accion, resultado, desde, hasta)
    return {"items": [_fila_auditoria(a) for a in q.offset((pagina - 1) * tamano).limit(tamano).all()],
            "total": q.count(), "pagina": pagina, "tamano": tamano}


@router.get("/auditoria.csv")
def exportar_auditoria(
    usuario: Optional[str] = None, modulo: Optional[str] = None, accion: Optional[str] = None,
    resultado: Optional[str] = Query(None, pattern="^(exito|fallo)$"), desde: Optional[date] = None, hasta: Optional[date] = None,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    filas = _consulta_auditoria(db, usuario, modulo, accion, resultado, desde, hasta).limit(getattr(settings, "MAX_FILAS_CSV", 20000)).all()
    return respuesta_csv(
        "Bitácora de auditoría", ["Fecha (UTC)", "Usuario", "IP", "Módulo", "Acción", "Entidad", "ID", "Resultado", "Detalle"],
        [(a.fecha, a.usuario_email or "", a.ip or "", a.modulo, a.accion, a.entidad or "", a.entidad_id or "", a.resultado, a.detalle or "") for a in filas],
        filtros={"usuario": usuario, "modulo": modulo, "accion": accion, "resultado": resultado, "desde": desde, "hasta": hasta},
        prefijo_archivo="auditoria",
    )


# ----------------------------------------------------------------- correo (punto 16)

class ConfigCorreoEntrada(BaseModel):
    habilitado: bool
    host: str = Field(max_length=200)
    puerto: int = Field(ge=1, le=65535)
    seguridad: str = Field(pattern="^(none|starttls|ssl)$")
    usuario: str = Field(default="", max_length=200)
    password: Optional[str] = Field(default=None, max_length=300, description="Vacío o ausente = conservar la actual")
    remitente_email: EmailStr
    remitente_nombre: str = Field(max_length=100)
    timeout_segundos: int = Field(ge=1, le=120)


def _config_publica(db) -> dict:
    cfg = email_service.configuracion_efectiva(db)
    return {k: v for k, v in cfg.items() if k != "password"} | {"password_configurada": bool(cfg["password"])}


@router.get("/config-correo")
def ver_config_correo(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    """Nunca devuelve la contraseña, solo si existe."""
    return _config_publica(db)


@router.put("/config-correo")
def guardar_config_correo(datos: ConfigCorreoEntrada, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    fila = db.get(ConfiguracionCorreo, 1) or ConfiguracionCorreo(id=1)
    db.add(fila)
    fila.habilitado, fila.host, fila.puerto, fila.seguridad, fila.usuario = datos.habilitado, datos.host.strip(), datos.puerto, datos.seguridad, datos.usuario.strip()
    fila.remitente_email, fila.remitente_nombre, fila.timeout_segundos = datos.remitente_email, datos.remitente_nombre.strip(), datos.timeout_segundos
    if datos.password:
        fila.password_cifrada = cifrar(datos.password)  # se guarda cifrada
    fila.actualizado_en = ahora()
    db.commit()
    audit.registrar(db, request, admin, "configuracion", "config_correo", despues={"host": fila.host, "puerto": fila.puerto, "habilitado": fila.habilitado})
    return _config_publica(db)


@router.post("/config-correo/probar")
def probar_config_correo(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    error = email_service.probar_conexion(db)
    if error:
        raise HTTPException(502, error)
    return {"mensaje": "La conexión con el servidor de correo funciona."}


class PlantillaEntrada(BaseModel):
    asunto: str = Field(min_length=3, max_length=200)
    cuerpo: str = Field(min_length=10, max_length=5000)


@router.get("/plantillas-correo")
def listar_plantillas(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    guardadas = {p.codigo: p for p in db.query(PlantillaCorreo).all()}
    salida = []
    for codigo, (asunto, cuerpo) in email_service.PLANTILLAS_POR_DEFECTO.items():
        p = guardadas.get(codigo)
        salida.append({"codigo": codigo, "asunto": p.asunto if p else asunto, "cuerpo": p.cuerpo if p else cuerpo, "personalizada": p is not None})
    return salida


@router.put("/plantillas-correo/{codigo}")
def guardar_plantilla(codigo: str, datos: PlantillaEntrada, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    if codigo not in email_service.PLANTILLAS_POR_DEFECTO:
        raise HTTPException(404, "No existe esa plantilla de correo.")
    fila = db.get(PlantillaCorreo, codigo) or PlantillaCorreo(codigo=codigo, asunto="", cuerpo="")
    db.add(fila)
    fila.asunto, fila.cuerpo = datos.asunto, datos.cuerpo
    db.commit()
    audit.registrar(db, request, admin, "configuracion", "plantilla_correo", entidad="plantilla", entidad_id=codigo)
    return {"mensaje": "Plantilla guardada."}


# ----------------------------------------------------------------- escala SUS (RF-08 / RNF-11)

@router.get("/sus")
def resumen_sus(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    filas = db.query(RespuestaSUS).all()
    puntajes = [f.puntaje for f in filas]
    promedio = round(sum(puntajes) / len(puntajes), 1) if puntajes else None
    return {"respuestas": len(puntajes), "puntaje_promedio": promedio, "cumple_objetivo_68": (promedio >= 68) if promedio is not None else None,
            "detalle": [{"usuario_id": f.usuario_id, "fecha": f.fecha, "puntaje": f.puntaje, "comentario": f.comentario} for f in filas]}
