from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, CheckConstraint

from core.database import Base
from core.tiempo import ahora


class ConfiguracionCorreo(Base):
    """Configuración SMTP editable desde la interfaz de administración (punto 16).
    La contraseña se guarda CIFRADA (Fernet derivada de SECRET_KEY) y nunca se devuelve."""

    __tablename__ = "configuracion_correo"
    __table_args__ = (CheckConstraint("id = 1", name="ck_config_correo_unica"),)

    id = Column(Integer, primary_key=True, default=1)
    habilitado = Column(Boolean, nullable=False, default=False)
    host = Column(String, nullable=False, default="")
    puerto = Column(Integer, nullable=False, default=587)
    seguridad = Column(String, nullable=False, default="starttls")
    usuario = Column(String, nullable=False, default="")
    password_cifrada = Column(Text, nullable=True)
    remitente_email = Column(String, nullable=False, default="no-reply@dermaseguimiento.local")
    remitente_nombre = Column(String, nullable=False, default="DermaSeguimiento")
    timeout_segundos = Column(Integer, nullable=False, default=10)
    actualizado_en = Column(DateTime, nullable=True, default=ahora)


class PlantillaCorreo(Base):
    __tablename__ = "plantillas_correo"

    codigo = Column(String, primary_key=True)
    asunto = Column(String, nullable=False)
    cuerpo = Column(Text, nullable=False)


class RespuestaSUS(Base):
    """Escala de usabilidad SUS aplicada a los dermatólogos de la prueba piloto (RF-08)."""

    __tablename__ = "respuestas_sus"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, nullable=False, index=True)
    fecha = Column(DateTime, nullable=False, default=ahora)
    respuestas = Column(String, nullable=False)  # "4,2,5,..." (10 valores de 1 a 5)
    puntaje = Column(Integer, nullable=False)
    comentario = Column(String, nullable=True)


class ConfiguracionSeguridad(Base):
    """Política de contraseñas editable por el administrador (fila única). Si no hay fila, o un
    campo está vacío, se usan los valores de las variables de entorno (PASSWORD_*)."""

    __tablename__ = "configuracion_seguridad"
    __table_args__ = (CheckConstraint("id = 1", name="ck_config_seguridad_unica"),)

    id = Column(Integer, primary_key=True, default=1)
    longitud_minima = Column(Integer, nullable=True)
    requiere_mayuscula = Column(Boolean, nullable=True)
    requiere_minuscula = Column(Boolean, nullable=True)
    requiere_numero = Column(Boolean, nullable=True)
    requiere_especial = Column(Boolean, nullable=True)
    max_dias_vigencia = Column(Integer, nullable=True)  # 0 = las contraseñas no vencen
    comunes_adicionales = Column(Text, nullable=True)   # contraseñas prohibidas extra, una por línea
    actualizado_en = Column(DateTime, nullable=True, default=ahora)
    actualizado_por = Column(Integer, nullable=True)


class IntentoLimitado(Base):
    """Un intento contra un endpoint con límite de frecuencia (login, registro, recuperación...).
    Guardarlo en la base hace que el límite se respete aunque haya varios procesos del servidor."""

    __tablename__ = "intentos_limitados"

    id = Column(Integer, primary_key=True)
    clave = Column(String, nullable=False, index=True)  # "<nombre>:<ip>"
    fecha = Column(DateTime, nullable=False, default=ahora, index=True)
