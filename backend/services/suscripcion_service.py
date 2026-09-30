"""Reglas de negocio de suscripciones, pagos, comprobantes y avisos (puntos 9 a 15)."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from core.tiempo import ahora
from models.suscripcion import (
    EST_ACTIVA, EST_CANCELADA, EST_PRUEBA, EST_VENCIDA, PAGO_APROBADO, PAGO_PENDIENTE,
    Comprobante, HistorialSuscripcion, Notificacion, Pago, Plan, Suscripcion,
)
from models.usuario import Usuario
from services import email_service
from services.letras import monto_en_letras
from services.pasarela import obtener_pasarela

CENT = Decimal("0.01")
ESTADOS_CON_ACCESO = (EST_PRUEBA, EST_ACTIVA, EST_CANCELADA)  # 'cancelada' conserva acceso hasta el vencimiento


def _dinero(x) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def plan_por_codigo(db: Session, codigo: str) -> Plan:
    plan = db.query(Plan).filter(Plan.codigo == codigo, Plan.activo.is_(True)).first()
    if not plan:
        raise HTTPException(404, "El plan elegido no existe o ya no está disponible. Elegí otro de la lista.")
    return plan


def _historial(db, susc, evento, anterior=None, nuevo=None, detalle=None):
    db.add(HistorialSuscripcion(
        suscripcion_id=susc.id, evento=evento, plan_anterior_id=anterior, plan_nuevo_id=nuevo, detalle=detalle,
    ))


# --------------------------------------------------------------------------- estado

def asegurar_suscripcion(db: Session, usuario: Usuario) -> Suscripcion:
    """Todo usuario tiene una suscripción: prueba premium (si TRIAL_DAYS > 0) o plan gratuito."""
    susc = db.query(Suscripcion).filter(Suscripcion.usuario_id == usuario.id).order_by(Suscripcion.id.desc()).first()
    if susc:
        return sincronizar(db, susc)
    ahora_ = ahora()
    premium = db.query(Plan).filter(Plan.incluye_procesamiento.is_(True), Plan.activo.is_(True)).order_by(Plan.precio).first()
    gratuito = db.query(Plan).filter(Plan.periodicidad == "gratuito").first()
    if settings.TRIAL_DAYS > 0 and premium:
        susc = Suscripcion(
            usuario_id=usuario.id, plan_id=premium.id, estado=EST_PRUEBA, es_prueba=True,
            fecha_inicio=ahora_, fecha_vencimiento=ahora_ + timedelta(days=settings.TRIAL_DAYS),
        )
        detalle = f"Período de prueba de {settings.TRIAL_DAYS} días"
    elif gratuito:
        susc = Suscripcion(usuario_id=usuario.id, plan_id=gratuito.id, estado=EST_ACTIVA, fecha_inicio=ahora_)
        detalle = "Plan gratuito"
    else:
        raise HTTPException(500, "El sistema todavía no tiene planes configurados. Contactá al administrador.")
    db.add(susc)
    db.flush()
    _historial(db, susc, "alta", None, susc.plan_id, detalle)
    db.commit()
    return susc


def sincronizar(db: Session, susc: Suscripcion) -> Suscripcion:
    """Aplica el vencimiento (RF-20): pasa a 'vencida' y aplica bajas programadas al plan gratuito."""
    if susc.estado in ESTADOS_CON_ACCESO and susc.fecha_vencimiento and susc.fecha_vencimiento <= ahora():
        anterior = susc.plan_id
        siguiente = db.get(Plan, susc.plan_siguiente_id) if susc.plan_siguiente_id else None
        if siguiente is not None and siguiente.periodicidad == "gratuito" and susc.estado != EST_CANCELADA:
            susc.plan_id, susc.plan_siguiente_id = siguiente.id, None
            susc.estado, susc.fecha_vencimiento, susc.es_prueba = EST_ACTIVA, None, False
            _historial(db, susc, "cambio_plan", anterior, siguiente.id, "Baja de plan programada aplicada")
        else:
            susc.estado = EST_VENCIDA
            _historial(db, susc, "vencimiento", anterior, None, "La suscripción venció")
        db.commit()
    return susc


def tiene_acceso_avanzado(db: Session, usuario: Usuario) -> bool:
    if not settings.ENFORCE_SUBSCRIPTION:
        return True
    susc = asegurar_suscripcion(db, usuario)
    plan = db.get(Plan, susc.plan_id)
    return bool(plan and plan.incluye_procesamiento and susc.estado in ESTADOS_CON_ACCESO)


def exigir_acceso_avanzado(db: Session, usuario: Usuario) -> None:
    if not tiene_acceso_avanzado(db, usuario):
        raise HTTPException(
            status_code=402,
            detail="Tu suscripción no incluye esta función o está vencida. Renová o elegí un plan Premium "
                   "desde la sección Suscripción. Mientras tanto podés seguir consultando tus pacientes.",
        )


def dias_restantes(susc: Suscripcion) -> Optional[int]:
    if susc.fecha_vencimiento is None:
        return None
    segundos = (susc.fecha_vencimiento - ahora()).total_seconds()
    return max(0, int(-(-segundos // 86400)))  # redondeo hacia arriba


def clasificar(susc: Suscripcion, hay_pago_pendiente: bool = False) -> str:
    """Categoría para la pantalla administrativa."""
    if susc.estado == EST_CANCELADA:
        return "cancelada"
    if susc.estado == EST_VENCIDA:
        return "pendiente_pago" if hay_pago_pendiente else "vencida"
    if susc.fecha_vencimiento and susc.fecha_vencimiento - ahora() <= timedelta(days=max(settings.avisos_dias or [7])):
        return "proxima_a_vencer"
    return "activa"


# --------------------------------------------------------------------------- cobro

def calcular_cobro(db: Session, susc: Suscripcion, nuevo: Plan) -> dict:
    """Define qué pasa al elegir `nuevo`: cobrar ahora, programar una baja o nada."""
    actual = db.get(Plan, susc.plan_id)
    vigente = susc.estado in ESTADOS_CON_ACCESO and (susc.fecha_vencimiento is None or susc.fecha_vencimiento > ahora())
    cero = Decimal("0.00")

    if nuevo.periodicidad == "gratuito":
        if not vigente or actual.periodicidad == "gratuito":
            return {"accion": "ninguna", "tipo": "cambio_plan", "monto": cero, "credito": cero}
        return {"accion": "programar", "tipo": "cambio_plan", "monto": cero, "credito": cero}

    if not vigente or actual.periodicidad == "gratuito" or susc.es_prueba:
        return {"accion": "cobrar", "tipo": "alta", "monto": _dinero(nuevo.precio), "credito": cero}

    if actual.id == nuevo.id:
        return {"accion": "cobrar", "tipo": "renovacion", "monto": _dinero(nuevo.precio), "credito": cero}

    if _dinero(nuevo.precio) < _dinero(actual.precio):
        return {"accion": "programar", "tipo": "cambio_plan", "monto": cero, "credito": cero}

    # Mejora de plan: se acredita el tiempo no usado del plan actual (prorrata por días)
    restantes = max(0.0, (susc.fecha_vencimiento - ahora()).total_seconds() / 86400) if susc.fecha_vencimiento else 0.0
    credito = _dinero(Decimal(str(actual.precio)) * Decimal(str(restantes)) / Decimal(actual.duracion_dias or 1))
    monto = max(cero, _dinero(nuevo.precio) - credito)
    return {"accion": "cobrar", "tipo": "cambio_plan", "monto": monto, "credito": credito}


def iniciar_cambio_o_pago(db: Session, usuario: Usuario, plan_codigo: str) -> dict:
    susc = asegurar_suscripcion(db, usuario)
    nuevo = plan_por_codigo(db, plan_codigo)
    calculo = calcular_cobro(db, susc, nuevo)

    if calculo["accion"] == "ninguna":
        raise HTTPException(409, "Ya estás en ese plan. No hace falta ningún cambio.")

    if calculo["accion"] == "programar":
        susc.plan_siguiente_id = nuevo.id
        _historial(db, susc, "baja_programada", susc.plan_id, nuevo.id,
                   "Cambio a un plan inferior: se aplicará al terminar el período pagado (sin reembolso)")
        db.commit()
        return {"accion": "programada", "mensaje": (
            f"Listo: pasarás al plan «{nuevo.nombre}» cuando termine tu período actual. Hasta entonces conservás tus funciones. "
            "No se realizan reembolsos por bajas de plan.")}

    if db.query(Pago).filter(Pago.suscripcion_id == susc.id, Pago.estado == PAGO_PENDIENTE, Pago.plan_id == nuevo.id).count():
        raise HTTPException(409, "Ya tenés un pago pendiente para este plan. Terminá ese pago o esperá unos minutos antes de iniciar otro.")

    if calculo["monto"] == 0:
        # El crédito cubre todo el importe: se aplica sin pasar por la pasarela
        pago = Pago(usuario_id=usuario.id, suscripcion_id=susc.id, plan_id=nuevo.id, tipo=calculo["tipo"], monto=Decimal("0.00"),
                    moneda=nuevo.moneda, estado=PAGO_APROBADO, proveedor="credito",
                    referencia_externa=f"CRD-{susc.id}-{int(ahora().timestamp())}", forma_pago="Crédito por tiempo no usado")
        db.add(pago)
        db.flush()
        aplicar_pago_aprobado(db, pago)
        return {"accion": "aplicada", "mensaje": f"Tu plan cambió a «{nuevo.nombre}». El crédito de tu plan anterior cubrió el importe."}

    pasarela = obtener_pasarela()
    referencia, url = pasarela.crear_operacion(calculo["monto"], nuevo.moneda, f"Suscripción {nuevo.nombre}")
    pago = Pago(usuario_id=usuario.id, suscripcion_id=susc.id, plan_id=nuevo.id, tipo=calculo["tipo"], monto=calculo["monto"],
                moneda=nuevo.moneda, estado=PAGO_PENDIENTE, proveedor=pasarela.nombre, referencia_externa=referencia)
    db.add(pago)
    db.commit()
    return {
        "accion": "pago", "pago_id": pago.id, "url_pago": url, "monto": str(calculo["monto"]),
        "credito": str(calculo["credito"]), "moneda": nuevo.moneda, "tipo": calculo["tipo"],
        "mensaje": f"Vas a pagar {calculo['monto']} {nuevo.moneda} por el plan «{nuevo.nombre}».",
    }


# --------------------------------------------------------------------------- pago aprobado

def aplicar_pago_aprobado(db: Session, pago: Pago) -> Comprobante:
    """Activa/extiende la suscripción, registra el historial y emite el comprobante.
    Se llama con el pago ya marcado como aprobado y dentro de la transacción del webhook."""
    susc = db.get(Suscripcion, pago.suscripcion_id)
    plan = db.get(Plan, pago.plan_id)
    usuario = db.get(Usuario, pago.usuario_id)
    ahora_ = ahora()
    anterior = susc.plan_id

    vigente = (
        susc.estado in (EST_ACTIVA, EST_CANCELADA) and susc.fecha_vencimiento
        and susc.fecha_vencimiento > ahora_ and not susc.es_prueba
    )
    if pago.tipo == "renovacion" and vigente:
        inicio = susc.fecha_vencimiento
    else:
        inicio = ahora_
        susc.fecha_inicio = ahora_
    susc.plan_id = plan.id
    susc.estado = EST_ACTIVA
    susc.es_prueba = False
    susc.fecha_vencimiento = inicio + timedelta(days=plan.duracion_dias) if plan.duracion_dias else None
    susc.plan_siguiente_id = None
    susc.cancelada_en = None
    susc.motivo_cancelacion = None
    evento = "renovacion" if pago.tipo == "renovacion" else ("cambio_plan" if pago.tipo == "cambio_plan" else "alta")
    _historial(db, susc, evento, anterior, plan.id, f"Pago {pago.referencia_externa} aprobado")

    periodo = None
    if susc.fecha_vencimiento:
        periodo = f"{inicio.date().isoformat()} al {susc.fecha_vencimiento.date().isoformat()}"
    comp = Comprobante(
        numero=f"TMP-{pago.id}-{int(ahora_.timestamp() * 1000)}", pago_id=pago.id, usuario_id=usuario.id, fecha_emision=ahora_,
        emisor_nombre=settings.EMISOR_NOMBRE, emisor_ruc=settings.EMISOR_RUC or None, emisor_email=settings.EMISOR_EMAIL,
        pagador_nombre=usuario.nombre, pagador_email=usuario.email, concepto=f"Suscripción {plan.nombre}",
        referencia=pago.referencia_externa, periodo=periodo, monto=pago.monto, moneda=pago.moneda,
        monto_letras=monto_en_letras(pago.monto, pago.moneda), forma_pago=pago.forma_pago or "No informada",
        leyenda=(f"Este recibo electrónico acredita únicamente la recepción del importe indicado y ha sido generado "
                 f"por el Sistema {settings.EMISOR_NOMBRE}. No constituye factura legal."),
    )
    db.add(comp)
    db.flush()
    comp.numero = f"REC-{comp.id:06d}"  # autonumerado por la clave primaria: no puede repetirse
    hasta = f" hasta el {susc.fecha_vencimiento.date().isoformat()}." if susc.fecha_vencimiento else "."
    mensaje = f"Recibimos tu pago de {pago.monto} {pago.moneda}. Tu plan «{plan.nombre}» está activo{hasta}"
    _crear_notificacion(db, usuario, f"pago:{pago.id}", "pago", mensaje)
    db.commit()
    email_service.enviar(db, usuario.email, "pago_aprobado", {"nombre": usuario.nombre, "mensaje": mensaje, "numero": comp.numero})
    return comp


# --------------------------------------------------------------------------- cancelación

def cancelar_suscripcion(db: Session, usuario: Usuario, motivo: str) -> Suscripcion:
    susc = asegurar_suscripcion(db, usuario)
    plan = db.get(Plan, susc.plan_id)
    if plan.periodicidad == "gratuito":
        raise HTTPException(409, "Tu plan es gratuito: no hay nada que cancelar.")
    if susc.estado == EST_CANCELADA:
        raise HTTPException(409, "Tu suscripción ya estaba cancelada.")
    if susc.estado == EST_VENCIDA:
        raise HTTPException(409, "Tu suscripción ya venció.")
    susc.estado = EST_CANCELADA
    susc.cancelada_en = ahora()
    susc.motivo_cancelacion = motivo
    susc.plan_siguiente_id = None
    _historial(db, susc, "cancelacion", susc.plan_id, None, motivo)
    db.commit()
    return susc


# --------------------------------------------------------------------------- avisos

def _crear_notificacion(db: Session, usuario: Usuario, clave: str, tipo: str, mensaje: str) -> Optional[Notificacion]:
    if db.query(Notificacion).filter(Notificacion.usuario_id == usuario.id, Notificacion.clave == clave).first():
        return None
    n = Notificacion(usuario_id=usuario.id, clave=clave, tipo=tipo, mensaje=mensaje)
    db.add(n)
    return n


def generar_avisos(db: Session, usuario: Usuario, enviar_correo: bool = True) -> list[Notificacion]:
    """Avisos anticipados (7/3/1 días, configurable) y posterior al vencimiento. Idempotente por hito."""
    susc = db.query(Suscripcion).filter(Suscripcion.usuario_id == usuario.id).order_by(Suscripcion.id.desc()).first()
    if not susc:
        return []
    susc = sincronizar(db, susc)
    plan = db.get(Plan, susc.plan_id)
    pendientes = []
    if plan and plan.periodicidad != "gratuito":
        if susc.estado in (EST_PRUEBA, EST_ACTIVA) and susc.fecha_vencimiento:
            quedan = (susc.fecha_vencimiento - ahora()).total_seconds() / 86400
            hitos = [d for d in settings.avisos_dias if quedan <= d]  # hito más cercano ya alcanzado
            if hitos:
                hito = min(hitos)
                dias = max(1, int(-(-quedan // 1)))
                que = "Tu período de prueba" if susc.es_prueba else f"Tu suscripción «{plan.nombre}»"
                msg = f"{que} vence en {dias} día{'s' if dias != 1 else ''} ({susc.fecha_vencimiento.date().isoformat()})."
                n = _crear_notificacion(db, usuario, f"venc:{susc.id}:{susc.fecha_vencimiento.date()}:{hito}", "vencimiento", msg)
                if n:
                    pendientes.append((n, "aviso_vencimiento", msg))
        elif susc.estado == EST_VENCIDA and susc.fecha_vencimiento:
            msg = (f"Tu suscripción «{plan.nombre}» venció el {susc.fecha_vencimiento.date().isoformat()}. "
                   "Las funciones avanzadas están bloqueadas hasta que la renueves.")
            n = _crear_notificacion(db, usuario, f"vencida:{susc.id}:{susc.fecha_vencimiento.date()}", "vencida", msg)
            if n:
                pendientes.append((n, "suscripcion_vencida", msg))
    db.commit()
    if enviar_correo:
        for n, codigo, msg in pendientes:
            if email_service.enviar(db, usuario.email, codigo, {"nombre": usuario.nombre, "mensaje": msg}):
                n.correo_enviado = True
        db.commit()
    return [n for n, _, _ in pendientes]
