from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey

from core.database import Base
from core.tiempo import ahora

ROL_ADMIN = "admin"
ROL_DERMATOLOGO = "dermatologo"
ROLES = (ROL_ADMIN, ROL_DERMATOLOGO)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    rol = Column(String, default=ROL_DERMATOLOGO, nullable=False)
    fecha_creacion = Column(DateTime, default=ahora)

    # Estado y trazabilidad del usuario (punto 2 de las recomendaciones)
    activo = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    fecha_modificacion = Column(DateTime, nullable=True)
    fecha_inactivacion = Column(DateTime, nullable=True)
    fecha_reactivacion = Column(DateTime, nullable=True)
    motivo_inactivacion = Column(String, nullable=True)

    # Seguridad de acceso
    intentos_fallidos = Column(Integer, nullable=False, default=0, server_default="0")
    bloqueado_hasta = Column(DateTime, nullable=True)
    password_cambiada_en = Column(DateTime, nullable=True)
    ultimo_acceso = Column(DateTime, nullable=True)

    # Confirmación del correo (las cuentas previas a esta función quedan como verificadas)
    email_verificado = Column(Boolean, nullable=False, default=True, server_default="true")
    email_verificado_en = Column(DateTime, nullable=True)

    # Consentimiento de la política de privacidad (última versión aceptada; el historial está en
    # consentimientos_usuario)
    politica_aceptada_version = Column(String, nullable=True)
    politica_aceptada_en = Column(DateTime, nullable=True)
    politica_finalidad = Column(String, nullable=True)
    consentimiento_revocado_en = Column(DateTime, nullable=True)
    anonimizado_en = Column(DateTime, nullable=True)  # baja solicitada por el titular o fin del plazo de retención


class Sesion(Base):
    """Una fila por token emitido. Permite cerrar sesión (invalidar el token),
    expirar por inactividad y revocar todas las sesiones de un usuario."""

    __tablename__ = "sesiones"

    id = Column(String, primary_key=True)  # jti del JWT
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    creada_en = Column(DateTime, nullable=False, default=ahora)
    ultimo_uso = Column(DateTime, nullable=False, default=ahora)
    expira_en = Column(DateTime, nullable=False)
    revocada = Column(Boolean, nullable=False, default=False, server_default="false")
    ip = Column(String, nullable=True)


TOKEN_RESTABLECER = "restablecer"
TOKEN_VERIFICAR = "verificar_email"


class TokenRestablecimiento(Base):
    """Token de un solo uso (recuperar contraseña o confirmar el correo). Se guarda solo el
    hash SHA-256; el token en claro únicamente viaja en el correo."""

    __tablename__ = "tokens_restablecimiento"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    creado_en = Column(DateTime, nullable=False, default=ahora)
    expira_en = Column(DateTime, nullable=False)
    usado_en = Column(DateTime, nullable=True)
    tipo = Column(String, nullable=False, default=TOKEN_RESTABLECER, server_default=TOKEN_RESTABLECER, index=True)


class ConsentimientoUsuario(Base):
    """Evidencia del consentimiento del profesional: qué versión de la política aceptó, cuándo,
    para qué finalidad y, si lo retiró, cuándo."""

    __tablename__ = "consentimientos_usuario"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    version_politica = Column(String, nullable=False)
    finalidad = Column(String, nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)
    ip = Column(String, nullable=True)
    revocado_en = Column(DateTime, nullable=True)
