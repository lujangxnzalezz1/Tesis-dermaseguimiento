"""Envío de correos con SMTP parametrizable (punto 16).

Prioridad de configuración: tabla `configuracion_correo` (editable por el admin)
y, si no hay fila, variables de entorno. Si el servicio está deshabilitado, el
mensaje se registra en el log del servidor (útil en desarrollo)."""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from string import Template
from typing import Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.crypto import descifrar
from models.configuracion import ConfiguracionCorreo, PlantillaCorreo

log = logging.getLogger("correo")

PLANTILLAS_POR_DEFECTO = {
    "restablecer_password": (
        "Restablecé tu contraseña de DermaSeguimiento",
        "Hola $nombre,\n\nRecibimos una solicitud para restablecer tu contraseña.\n"
        "Usá este enlace (vale $minutos minutos y solo puede usarse una vez):\n\n$enlace\n\n"
        "Si no lo pediste vos, ignorá este mensaje: tu contraseña no cambió.\n",
    ),
    "verificar_email": (
        "Confirmá tu correo en DermaSeguimiento",
        "Hola $nombre,\n\nPara activar tu cuenta, confirmá que este es tu correo abriendo este enlace "
        "(vale $horas horas y se puede usar una sola vez):\n\n$enlace\n\n"
        "Si no creaste una cuenta en DermaSeguimiento, ignorá este mensaje.\n",
    ),
    "aviso_vencimiento": (
        "Tu suscripción vence pronto",
        "Hola $nombre,\n\n$mensaje\n\nPodés renovar o cambiar de plan desde la sección Suscripción de la app.\n",
    ),
    "suscripcion_vencida": (
        "Tu suscripción venció",
        "Hola $nombre,\n\n$mensaje\n\nMientras tanto podés seguir consultando la información de tus pacientes.\n",
    ),
    "pago_aprobado": (
        "Recibimos tu pago",
        "Hola $nombre,\n\n$mensaje\n\nEl comprobante $numero está disponible en la sección Suscripción.\n",
    ),
}


def configuracion_efectiva(db: Session) -> dict:
    fila = db.query(ConfiguracionCorreo).filter(ConfiguracionCorreo.id == 1).first()
    if fila:
        return {
            "habilitado": fila.habilitado, "host": fila.host, "puerto": fila.puerto,
            "seguridad": fila.seguridad, "usuario": fila.usuario,
            "password": descifrar(fila.password_cifrada) if fila.password_cifrada else "",
            "remitente_email": fila.remitente_email, "remitente_nombre": fila.remitente_nombre,
            "timeout": fila.timeout_segundos,
        }
    return {
        "habilitado": settings.SMTP_ENABLED, "host": settings.SMTP_HOST, "puerto": settings.SMTP_PORT,
        "seguridad": settings.SMTP_SECURITY, "usuario": settings.SMTP_USER, "password": settings.SMTP_PASSWORD,
        "remitente_email": settings.SMTP_FROM_EMAIL, "remitente_nombre": settings.SMTP_FROM_NAME,
        "timeout": settings.SMTP_TIMEOUT_SECONDS,
    }


def _plantilla(db: Session, codigo: str) -> tuple[str, str]:
    fila = db.query(PlantillaCorreo).filter(PlantillaCorreo.codigo == codigo).first()
    if fila:
        return fila.asunto, fila.cuerpo
    return PLANTILLAS_POR_DEFECTO[codigo]


def enviar(db: Session, destinatario: str, codigo: str, contexto: dict) -> bool:
    """Devuelve True si el correo salió por SMTP. Nunca lanza excepciones al llamador."""
    asunto_t, cuerpo_t = _plantilla(db, codigo)
    asunto = Template(asunto_t).safe_substitute(contexto)
    cuerpo = Template(cuerpo_t).safe_substitute(contexto)
    cfg = configuracion_efectiva(db)

    if not (cfg["habilitado"] and cfg["host"]):
        log.warning("[CORREO DESHABILITADO] Para: %s | Asunto: %s\n%s", destinatario, asunto, cuerpo)
        return False

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = formataddr((cfg["remitente_nombre"], cfg["remitente_email"]))
    mensaje["To"] = destinatario
    mensaje.set_content(cuerpo)
    try:
        if cfg["seguridad"] == "ssl":
            servidor: smtplib.SMTP = smtplib.SMTP_SSL(
                cfg["host"], cfg["puerto"], timeout=cfg["timeout"], context=ssl.create_default_context()
            )
        else:
            servidor = smtplib.SMTP(cfg["host"], cfg["puerto"], timeout=cfg["timeout"])
            if cfg["seguridad"] == "starttls":
                servidor.starttls(context=ssl.create_default_context())
        with servidor:
            if cfg["usuario"]:
                servidor.login(cfg["usuario"], cfg["password"])
            servidor.send_message(mensaje)
        return True
    except Exception:
        log.exception("No se pudo enviar el correo a %s", destinatario)
        return False


def probar_conexion(db: Session) -> Optional[str]:
    """Devuelve None si la conexión SMTP funciona, o un mensaje amable si falla."""
    cfg = configuracion_efectiva(db)
    if not cfg["host"]:
        return "Falta configurar el servidor SMTP."
    try:
        if cfg["seguridad"] == "ssl":
            s = smtplib.SMTP_SSL(cfg["host"], cfg["puerto"], timeout=cfg["timeout"])
        else:
            s = smtplib.SMTP(cfg["host"], cfg["puerto"], timeout=cfg["timeout"])
            if cfg["seguridad"] == "starttls":
                s.starttls(context=ssl.create_default_context())
        with s:
            if cfg["usuario"]:
                s.login(cfg["usuario"], cfg["password"])
        return None
    except Exception:
        log.exception("Prueba de conexión SMTP fallida")
        return "No se pudo conectar con el servidor de correo. Revisá servidor, puerto, cifrado y credenciales."
