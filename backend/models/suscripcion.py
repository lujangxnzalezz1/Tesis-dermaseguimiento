from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, event, inspect, select, text,
)

from core.database import Base
from core.tiempo import ahora

# Estados de la suscripción
EST_PRUEBA = "prueba"
EST_ACTIVA = "activa"
EST_PENDIENTE = "pendiente_pago"
EST_VENCIDA = "vencida"
EST_CANCELADA = "cancelada"

# Estados del pago
PAGO_PENDIENTE = "pendiente"
PAGO_APROBADO = "aprobado"
PAGO_RECHAZADO = "rechazado"
PAGO_CANCELADO = "cancelado"
PAGO_VENCIDO = "vencido"  # la deuda en la pasarela expiró sin pagarse
ESTADOS_PAGO = (PAGO_PENDIENTE, PAGO_APROBADO, PAGO_RECHAZADO, PAGO_CANCELADO, PAGO_VENCIDO)

# Estados del comprobante (las reimpresiones se cuentan aparte: no cambian el estado)
COMP_EMITIDO = "emitido"
COMP_ANULADO = "anulado"


class Plan(Base):
    __tablename__ = "planes"

    id = Column(Integer, primary_key=True)
    codigo = Column(String, unique=True, nullable=False)
    nombre = Column(String, nullable=False)
    precio = Column(Numeric(10, 2), nullable=False, default=0)
    moneda = Column(String, nullable=False, default="PYG")
    periodicidad = Column(String, nullable=False)  # gratuito | mensual | anual
    duracion_dias = Column(Integer, nullable=False, default=0)  # 0 = sin vencimiento
    funcionalidades = Column(Text, nullable=False, default="[]")  # JSON: lista de textos
    limites = Column(Text, nullable=False, default="[]")  # JSON: lista de textos
    condiciones = Column(Text, nullable=False, default="")
    incluye_procesamiento = Column(Boolean, nullable=False, default=False)
    activo = Column(Boolean, nullable=False, default=True)
    orden = Column(Integer, nullable=False, default=0)


class Suscripcion(Base):
    __tablename__ = "suscripciones"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("planes.id"), nullable=False)
    estado = Column(String, nullable=False, index=True)
    fecha_inicio = Column(DateTime, nullable=False, default=ahora)
    fecha_vencimiento = Column(DateTime, nullable=True, index=True)  # None = sin vencimiento
    es_prueba = Column(Boolean, nullable=False, default=False)
    cancelada_en = Column(DateTime, nullable=True)
    motivo_cancelacion = Column(String, nullable=True)
    plan_siguiente_id = Column(Integer, ForeignKey("planes.id"), nullable=True)  # baja de plan programada
    creada_en = Column(DateTime, nullable=False, default=ahora)


class HistorialSuscripcion(Base):
    """Renovaciones, cancelaciones y cambios de plan (RF-19)."""

    __tablename__ = "historial_suscripciones"

    id = Column(Integer, primary_key=True)
    suscripcion_id = Column(Integer, ForeignKey("suscripciones.id"), nullable=False, index=True)
    fecha = Column(DateTime, nullable=False, default=ahora)
    evento = Column(String, nullable=False)  # alta | renovacion | cambio_plan | cancelacion | vencimiento | baja_programada
    plan_anterior_id = Column(Integer, nullable=True)
    plan_nuevo_id = Column(Integer, nullable=True)
    detalle = Column(String, nullable=True)


class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    suscripcion_id = Column(Integer, ForeignKey("suscripciones.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("planes.id"), nullable=False)
    tipo = Column(String, nullable=False)  # alta | renovacion | cambio_plan
    monto = Column(Numeric(10, 2), nullable=False)
    moneda = Column(String, nullable=False, default="USD")
    estado = Column(String, nullable=False, default=PAGO_PENDIENTE, index=True)
    proveedor = Column(String, nullable=False)
    referencia_externa = Column(String, unique=True, nullable=False, index=True)  # id de la operación en la pasarela
    forma_pago = Column(String, nullable=True)
    credito = Column(Numeric(10, 2), nullable=True)  # crédito por tiempo no usado ya descontado del monto
    transaccion_id = Column(String, nullable=True)  # id de la transacción informado por la pasarela (AdamsPay)
    pagador_documento = Column(String, nullable=True)  # RUC o CI para el recibo (opcional)
    pagador_telefono = Column(String, nullable=True)
    creado_en = Column(DateTime, nullable=False, default=ahora)
    actualizado_en = Column(DateTime, nullable=True)
    ultimo_evento_id = Column(String, nullable=True)


class Comprobante(Base):
    """Recibo electrónico (NO es factura legal). Inmutable: las correcciones se
    hacen anulando y emitiendo otro (con otro número) para el mismo pago."""

    __tablename__ = "comprobantes"
    __table_args__ = (
        # Un pago tiene a lo sumo UN comprobante vigente; los anulados quedan como constancia
        Index("uq_comprobante_pago_vigente", "pago_id", unique=True,
              postgresql_where=text("estado <> 'anulado'"), sqlite_where=text("estado <> 'anulado'")),
    )

    id = Column(Integer, primary_key=True)
    numero = Column(String, unique=True, nullable=False, index=True)
    pago_id = Column(Integer, ForeignKey("pagos.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    fecha_emision = Column(DateTime, nullable=False, default=ahora)
    estado = Column(String, nullable=False, default=COMP_EMITIDO)  # emitido | anulado («reimpreso» solo en registros viejos)
    emisor_nombre = Column(String, nullable=False)
    emisor_ruc = Column(String, nullable=True)
    emisor_email = Column(String, nullable=True)
    pagador_nombre = Column(String, nullable=False)
    pagador_email = Column(String, nullable=False)
    pagador_documento = Column(String, nullable=True)  # RUC o CI, si el usuario lo informó al pagar
    pagador_telefono = Column(String, nullable=True)
    concepto = Column(String, nullable=False)
    referencia = Column(String, nullable=False)
    periodo = Column(String, nullable=True)
    monto = Column(Numeric(10, 2), nullable=False)
    moneda = Column(String, nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=True)  # precio del plan antes del crédito
    credito = Column(Numeric(10, 2), nullable=True)   # crédito por tiempo no usado aplicado
    iva = Column(Numeric(10, 2), nullable=True)       # IVA 10 % incluido en el total (total / 11)
    monto_letras = Column(String, nullable=False)
    forma_pago = Column(String, nullable=False)
    leyenda = Column(String, nullable=False)
    anulado_en = Column(DateTime, nullable=True)
    anulado_por = Column(Integer, nullable=True)
    motivo_anulacion = Column(String, nullable=True)
    reimpresiones = Column(Integer, nullable=False, default=0)  # veces que se descargó (más de 1 = reimpresión)
    reimpreso_en = Column(DateTime, nullable=True)  # fecha de la última reimpresión


# Lo único que puede cambiar en un comprobante emitido: contadores de reimpresión, el número
# definitivo al crearlo (reemplaza al provisorio TMP-) y los datos de la anulación.
_CAMPOS_REIMPRESION = {"reimpresiones", "reimpreso_en"}
_CAMPOS_ANULACION = {"estado", "anulado_en", "anulado_por", "motivo_anulacion"}


@event.listens_for(Comprobante, "before_update")
def _comprobante_inmutable(mapper, connection, target):
    previo = connection.execute(select(Comprobante.__table__.c.estado).where(Comprobante.__table__.c.id == target.id)).scalar()
    if previo == COMP_ANULADO:
        raise PermissionError("Un comprobante anulado no puede modificarse. Emití uno nuevo para el mismo pago.")
    for atributo in inspect(target).attrs:
        historia = atributo.history
        if not historia.has_changes():
            continue
        campo = atributo.key
        if campo in _CAMPOS_REIMPRESION:
            continue
        if campo == "numero" and historia.deleted and str(historia.deleted[0]).startswith("TMP-"):
            continue
        if campo in _CAMPOS_ANULACION and target.estado == COMP_ANULADO:
            continue
        raise PermissionError(f"El comprobante no puede modificarse (campo «{campo}»): se anula y se emite otro.")


@event.listens_for(Comprobante, "before_delete")
def _comprobante_no_se_borra(mapper, connection, target):
    raise PermissionError("Los comprobantes no se eliminan: se anulan.")


class Notificacion(Base):
    __tablename__ = "notificaciones"
    __table_args__ = (UniqueConstraint("usuario_id", "clave", name="uq_notificacion_clave"),)

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    clave = Column(String, nullable=False)  # evita avisos repetidos para el mismo hito
    tipo = Column(String, nullable=False)
    mensaje = Column(String, nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)
    leida = Column(Boolean, nullable=False, default=False)
    correo_enviado = Column(Boolean, nullable=False, default=False)
