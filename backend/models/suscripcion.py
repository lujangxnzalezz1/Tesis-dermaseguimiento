from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
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
    referencia_externa = Column(String, unique=True, nullable=False, index=True)  # id de transacción de la pasarela
    forma_pago = Column(String, nullable=True)
    creado_en = Column(DateTime, nullable=False, default=ahora)
    actualizado_en = Column(DateTime, nullable=True)
    ultimo_evento_id = Column(String, nullable=True)


class Comprobante(Base):
    """Recibo electrónico (NO es factura legal). Inmutable: las correcciones se
    hacen anulando y emitiendo otro."""

    __tablename__ = "comprobantes"

    id = Column(Integer, primary_key=True)
    numero = Column(String, unique=True, nullable=False, index=True)
    pago_id = Column(Integer, ForeignKey("pagos.id"), unique=True, nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    fecha_emision = Column(DateTime, nullable=False, default=ahora)
    estado = Column(String, nullable=False, default="emitido")  # emitido | anulado | reimpreso
    emisor_nombre = Column(String, nullable=False)
    emisor_ruc = Column(String, nullable=True)
    emisor_email = Column(String, nullable=True)
    pagador_nombre = Column(String, nullable=False)
    pagador_email = Column(String, nullable=False)
    concepto = Column(String, nullable=False)
    referencia = Column(String, nullable=False)
    periodo = Column(String, nullable=True)
    monto = Column(Numeric(10, 2), nullable=False)
    moneda = Column(String, nullable=False)
    monto_letras = Column(String, nullable=False)
    forma_pago = Column(String, nullable=False)
    leyenda = Column(String, nullable=False)
    anulado_en = Column(DateTime, nullable=True)
    anulado_por = Column(Integer, nullable=True)
    motivo_anulacion = Column(String, nullable=True)
    reimpresiones = Column(Integer, nullable=False, default=0)


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
