"""Reglas de negocio de suscripciones, pagos, comprobantes y avisos (puntos 9 a 15)."""
import logging
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.tiempo import ahora
from models.suscripcion import (
    COMP_ANULADO, EST_ACTIVA, EST_CANCELADA, EST_PRUEBA, EST_VENCIDA, PAGO_APROBADO, PAGO_CANCELADO, PAGO_PENDIENTE,
    PAGO_VENCIDO, Comprobante, HistorialSuscripcion, Notificacion, Pago, Plan, Suscripcion,
)
from models.usuario import Usuario
from services import auditoria_service as audit
from services import email_service, push_service
from services.letras import formato_monto, monto_en_letras
from services.pasarela import ErrorPasarela, obtener_pasarela

log = logging.getLogger("pagos")
CENT = Decimal("0.01")
ESTADOS_CON_ACCESO = (EST_PRUEBA, EST_ACTIVA, EST_CANCELADA)  # 'cancelada' conserva acceso hasta el vencimiento


def _dinero(x, moneda: str = "PYG") -> Decimal:
    """Redondeo según la moneda: el guaraní no tiene centavos."""
    return Decimal(str(x)).quantize(Decimal("1") if moneda == "PYG" else CENT, rounding=ROUND_HALF_UP)


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

def asegurar_suscripcion(db: Session, usuario: Usuario, confirmar: bool = True) -> Suscripcion:
    """Todo usuario tiene una suscripción: prueba premium (si TRIAL_DAYS > 0) o plan gratuito.
    Con confirmar=False no hace commit, para que el registro guarde usuario y suscripción juntos."""
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
    try:
        db.flush()
    except IntegrityError:
        # Otra solicitud creó la suscripción al mismo tiempo (usuario_id es único): se usa esa
        db.rollback()
        return db.query(Suscripcion).filter(Suscripcion.usuario_id == usuario.id).one()
    _historial(db, susc, "alta", None, susc.plan_id, detalle)
    if confirmar:
        db.commit()
    return susc


def sincronizar(db: Session, susc: Suscripcion) -> Suscripcion:
    """Aplica el vencimiento (RF-20): pasa a 'vencida' y aplica las bajas de plan programadas.
    Baja al gratuito: queda activa sin vencimiento. Baja a otro plan pago (p. ej. anual → mensual):
    se cambia el plan y la suscripción queda 'vencida' hasta que se pague el nuevo período."""
    if susc.estado in ESTADOS_CON_ACCESO and susc.fecha_vencimiento and susc.fecha_vencimiento <= ahora():
        anterior = susc.plan_id
        siguiente = db.get(Plan, susc.plan_siguiente_id) if susc.plan_siguiente_id else None
        if siguiente is not None and siguiente.periodicidad == "gratuito" and susc.estado != EST_CANCELADA:
            susc.plan_id, susc.plan_siguiente_id = siguiente.id, None
            susc.estado, susc.fecha_vencimiento, susc.es_prueba = EST_ACTIVA, None, False
            _historial(db, susc, "cambio_plan", anterior, siguiente.id, "Baja de plan programada aplicada")
        elif siguiente is not None and susc.estado != EST_CANCELADA:
            susc.plan_id, susc.plan_siguiente_id = siguiente.id, None
            susc.estado, susc.es_prueba = EST_VENCIDA, False
            _historial(db, susc, "cambio_plan", anterior, siguiente.id,
                       "Baja de plan programada aplicada: el nuevo plan queda pendiente de pago")
            _historial(db, susc, "vencimiento", anterior, None, "La suscripción venció")
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
        return {"accion": "cobrar", "tipo": "alta", "monto": _dinero(nuevo.precio, nuevo.moneda), "credito": cero}

    if actual.id == nuevo.id:
        return {"accion": "cobrar", "tipo": "renovacion", "monto": _dinero(nuevo.precio, nuevo.moneda), "credito": cero}

    if _dinero(nuevo.precio, nuevo.moneda) < _dinero(actual.precio, actual.moneda):
        return {"accion": "programar", "tipo": "cambio_plan", "monto": cero, "credito": cero}

    # Mejora de plan: se acredita el tiempo no usado del plan actual (prorrata por días)
    restantes = max(0.0, (susc.fecha_vencimiento - ahora()).total_seconds() / 86400) if susc.fecha_vencimiento else 0.0
    credito = _dinero(Decimal(str(actual.precio)) * Decimal(str(restantes)) / Decimal(actual.duracion_dias or 1), nuevo.moneda)
    monto = max(cero, _dinero(nuevo.precio, nuevo.moneda) - credito)
    return {"accion": "cobrar", "tipo": "cambio_plan", "monto": monto, "credito": credito}


def cotizar(db: Session, usuario: Usuario, plan_codigo: str) -> dict:
    """Lo que costaría elegir el plan (sin crear ningún pago): la app lo muestra antes de ir a la pasarela."""
    susc = asegurar_suscripcion(db, usuario)
    nuevo = plan_por_codigo(db, plan_codigo)
    calculo = calcular_cobro(db, susc, nuevo)
    moneda = nuevo.moneda
    precio = _dinero(nuevo.precio, moneda)
    return {
        "accion": calculo["accion"], "tipo": calculo["tipo"], "plan": nuevo.codigo, "plan_nombre": nuevo.nombre,
        "moneda": moneda, "precio": str(precio), "credito": str(_dinero(calculo["credito"], moneda)),
        "monto": str(_dinero(calculo["monto"], moneda)), "iva_incluido": str(iva_incluido(calculo["monto"], moneda)),
    }


def iva_incluido(total, moneda: str = "PYG") -> Decimal:
    """IVA 10 % contenido en un precio con IVA incluido (Paraguay): total / 11."""
    return _dinero(Decimal(str(total)) / Decimal(11), moneda)


def _pagos_pendientes_vigentes(db: Session, susc: Suscripcion, plan: Plan) -> int:
    """Pagos pendientes que bloquean un nuevo checkout. Antes se consulta a la pasarela: una deuda
    vencida o cancelada en AdamsPay deja de bloquear (si no hay conexión, se sigue bloqueando)."""
    pendientes = db.query(Pago).filter(Pago.suscripcion_id == susc.id, Pago.estado == PAGO_PENDIENTE, Pago.plan_id == plan.id).all()
    for pago in pendientes:
        try:
            verificar_pago_externo(db, pago)
        except HTTPException:
            pass
    return db.query(Pago).filter(Pago.suscripcion_id == susc.id, Pago.estado == PAGO_PENDIENTE, Pago.plan_id == plan.id).count()


def iniciar_cambio_o_pago(db: Session, usuario: Usuario, plan_codigo: str,
                          documento: Optional[str] = None, telefono: Optional[str] = None) -> dict:
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

    if _pagos_pendientes_vigentes(db, susc, nuevo):
        raise HTTPException(409, "Ya tenés un pago pendiente para este plan. Terminá ese pago o esperá unos minutos antes de iniciar otro.")

    if calculo["monto"] == 0:
        # El crédito cubre todo el importe: se aplica sin pasar por la pasarela
        pago = Pago(usuario_id=usuario.id, suscripcion_id=susc.id, plan_id=nuevo.id, tipo=calculo["tipo"], monto=Decimal("0.00"),
                    moneda=nuevo.moneda, estado=PAGO_APROBADO, proveedor="credito",
                    referencia_externa=f"CRD-{susc.id}-{int(ahora().timestamp())}", forma_pago="Crédito por tiempo no usado",
                    credito=calculo["credito"], pagador_documento=documento, pagador_telefono=telefono)
        db.add(pago)
        db.flush()
        aplicar_pago_aprobado(db, pago)
        return {"accion": "aplicada", "mensaje": f"Tu plan cambió a «{nuevo.nombre}». El crédito de tu plan anterior cubrió el importe."}

    pasarela = obtener_pasarela()
    try:
        referencia, url = pasarela.crear_operacion(calculo["monto"], nuevo.moneda, f"Suscripción {nuevo.nombre}")
    except ErrorPasarela:
        raise HTTPException(502, "No pudimos conectar con la pasarela de pagos. Intentá de nuevo en unos minutos; no se realizó ningún cobro.")
    pago = Pago(usuario_id=usuario.id, suscripcion_id=susc.id, plan_id=nuevo.id, tipo=calculo["tipo"], monto=calculo["monto"],
                moneda=nuevo.moneda, estado=PAGO_PENDIENTE, proveedor=pasarela.nombre, referencia_externa=referencia,
                credito=calculo["credito"], pagador_documento=documento, pagador_telefono=telefono)
    db.add(pago)
    db.commit()
    return {
        "accion": "pago", "pago_id": pago.id, "url_pago": url, "monto": str(calculo["monto"]),
        "credito": str(calculo["credito"]), "moneda": nuevo.moneda, "tipo": calculo["tipo"],
        "mensaje": f"Vas a pagar {formato_monto(calculo['monto'], nuevo.moneda)} por el plan «{nuevo.nombre}».",
    }


# --------------------------------------------------------------------------- pago aprobado

ERROR_CONSULTA = ("No pudimos consultar el estado de tu pago con la pasarela. Tu pago sigue pendiente y no se "
                  "cobró dos veces; volvé a intentar en unos minutos.")


def verificar_pago_externo(db: Session, pago: Pago) -> Pago:
    """Para pasarelas que se consultan (AdamsPay). Pagada y con el monto correcto → aprueba el pago una
    sola vez; cancelada o vencida → cierra el pago local (así se puede iniciar otro checkout); en otro
    caso sigue pendiente. Si no hay conexión con la pasarela responde 503 sin tocar el pago."""
    if pago.estado != PAGO_PENDIENTE or pago.proveedor != "adamspay":
        return pago
    pasarela = obtener_pasarela()
    if not hasattr(pasarela, "consultar"):
        return pago
    try:
        estado = pasarela.consultar(pago.referencia_externa)
    except ErrorPasarela as e:
        log.warning("No se pudo consultar el pago %s: %s", pago.id, e)
        raise HTTPException(503, ERROR_CONSULTA)
    if estado["estado"] == PAGO_PENDIENTE:
        return pago
    pago = db.query(Pago).filter(Pago.id == pago.id).with_for_update().first()
    if pago.estado != PAGO_PENDIENTE:
        return pago  # otra consulta simultánea ya lo resolvió
    referencia = {"referencia": pago.referencia_externa, "monto": str(pago.monto), "transaccion": estado.get("transaccion_id")}

    if estado["estado"] in (PAGO_CANCELADO, PAGO_VENCIDO):
        pago.estado = estado["estado"]
        pago.actualizado_en = ahora()
        db.commit()
        audit.registrar(db, None, None, "pagos", f"pago_{pago.estado}", entidad="pago", entidad_id=pago.id,
                        usuario_id=pago.usuario_id, despues=referencia, detalle="informado por AdamsPay al consultar la deuda")
        return pago

    if estado["monto"] != Decimal(pago.monto) or estado["moneda"] != pago.moneda:
        # No se aprueba un pago cuyo monto no coincide: queda pendiente para revisión manual
        audit.registrar(db, None, None, "pagos", "verificar_pago", entidad="pago", entidad_id=pago.id, usuario_id=pago.usuario_id,
                        resultado="fallo", detalle=f"AdamsPay informó {estado['monto']} {estado['moneda']}; se esperaba {pago.monto} {pago.moneda}")
        return pago
    pago.estado = PAGO_APROBADO
    pago.forma_pago = f"AdamsPay — {estado['forma_pago']}" if estado.get("forma_pago") else "AdamsPay"
    pago.transaccion_id = estado.get("transaccion_id")
    pago.actualizado_en = ahora()
    db.flush()
    aplicar_pago_aprobado(db, pago)
    audit.registrar(db, None, None, "pagos", "pago_aprobado", entidad="pago", entidad_id=pago.id, usuario_id=pago.usuario_id,
                    despues=referencia, detalle="confirmado consultando a AdamsPay")
    return pago


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
    comp = _emitir_comprobante(db, pago, usuario, f"Suscripción {plan.nombre}", periodo)
    hasta = f" hasta el {susc.fecha_vencimiento.date().isoformat()}." if susc.fecha_vencimiento else "."
    mensaje = f"Recibimos tu pago de {formato_monto(pago.monto, pago.moneda)}. Tu plan «{plan.nombre}» está activo{hasta}"
    _crear_notificacion(db, usuario, f"pago:{pago.id}", "pago", mensaje)
    db.commit()
    email_service.enviar(db, usuario.email, "pago_aprobado", {"nombre": usuario.nombre, "mensaje": mensaje, "numero": comp.numero})
    push_service.enviar(usuario.id, "Pago recibido", mensaje)
    return comp


# --------------------------------------------------------------------------- comprobantes

LEYENDA = ("Este recibo electrónico acredita únicamente la recepción del importe indicado y ha sido generado "
           "por el Sistema {emisor}. No constituye factura legal.")


def _emitir_comprobante(db: Session, pago: Pago, usuario: Usuario, concepto: str, periodo: Optional[str]) -> Comprobante:
    ahora_ = ahora()
    credito = _dinero(pago.credito or 0, pago.moneda)
    comp = Comprobante(
        numero=f"TMP-{pago.id}-{int(ahora_.timestamp() * 1000)}", pago_id=pago.id, usuario_id=usuario.id, fecha_emision=ahora_,
        emisor_nombre=settings.EMISOR_NOMBRE, emisor_ruc=settings.EMISOR_RUC or None, emisor_email=settings.EMISOR_EMAIL,
        pagador_nombre=usuario.nombre, pagador_email=usuario.email,
        pagador_documento=pago.pagador_documento, pagador_telefono=pago.pagador_telefono, concepto=concepto,
        referencia=pago.referencia_externa, periodo=periodo, monto=pago.monto, moneda=pago.moneda,
        subtotal=_dinero(pago.monto, pago.moneda) + credito, credito=credito, iva=iva_incluido(pago.monto, pago.moneda),
        monto_letras=monto_en_letras(pago.monto, pago.moneda), forma_pago=pago.forma_pago or "No informada",
        leyenda=LEYENDA.format(emisor=settings.EMISOR_NOMBRE),
    )
    db.add(comp)
    db.flush()
    comp.numero = f"REC-{comp.id:06d}"  # autonumerado por la clave primaria: no puede repetirse
    return comp


def comprobante_vigente(db: Session, pago_id: int) -> Optional[Comprobante]:
    """El comprobante no anulado del pago (o el último anulado, si no se emitió otro)."""
    filas = db.query(Comprobante).filter(Comprobante.pago_id == pago_id).order_by(Comprobante.id.desc()).all()
    return next((c for c in filas if c.estado != COMP_ANULADO), filas[0] if filas else None)


def reemitir_comprobante(db: Session, comprobante_id: int) -> Comprobante:
    """Tras anular un comprobante se emite OTRO (número nuevo) para el mismo pago. El anulado no se toca."""
    anulado = db.get(Comprobante, comprobante_id)
    if not anulado:
        raise HTTPException(404, "No encontramos ese comprobante.")
    if anulado.estado != COMP_ANULADO:
        raise HTTPException(409, "Solo se puede emitir un comprobante nuevo cuando el anterior está anulado. Anulalo primero.")
    pago = db.get(Pago, anulado.pago_id)
    if pago is None or pago.estado != PAGO_APROBADO:
        raise HTTPException(409, "El pago de ese comprobante no está aprobado: no corresponde emitir un recibo.")
    if db.query(Comprobante).filter(Comprobante.pago_id == pago.id, Comprobante.estado != COMP_ANULADO).count():
        raise HTTPException(409, "Ese pago ya tiene un comprobante vigente.")
    usuario = db.get(Usuario, pago.usuario_id)
    comp = _emitir_comprobante(db, pago, usuario, anulado.concepto, anulado.periodo)
    db.commit()
    return comp


def registrar_impresion(db: Session, comp: Comprobante) -> bool:
    """Cuenta las impresiones sin cambiar el estado (sigue «emitido») y devuelve True si es una
    reimpresión. Un comprobante anulado se puede descargar con la marca ANULADO, pero no se modifica."""
    if comp.estado == COMP_ANULADO:
        return (comp.reimpresiones or 0) > 0
    comp.reimpresiones = (comp.reimpresiones or 0) + 1
    reimpreso = comp.reimpresiones > 1
    if reimpreso:
        comp.reimpreso_en = ahora()
    db.commit()
    return reimpreso


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
    for n, _, msg in pendientes:
        push_service.enviar(usuario.id, "Tu suscripción", msg)
    if enviar_correo:
        for n, codigo, msg in pendientes:
            if email_service.enviar(db, usuario.email, codigo, {"nombre": usuario.nombre, "mensaje": msg}):
                n.correo_enviado = True
        db.commit()
    return [n for n, _, _ in pendientes]
