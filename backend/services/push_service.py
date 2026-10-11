"""Notificaciones push con OneSignal (API REST).

Se envían al usuario por su id (el mismo `external_id` con el que la app llama a `OneSignal.login`).
Sin ONESIGNAL_APP_ID u ONESIGNAL_REST_API_KEY no se envía nada: el aviso queda igual en la app y por correo.
Un fallo de OneSignal nunca interrumpe la operación que generó el aviso.
"""
import json
import logging
import urllib.request

from core.config import settings

log = logging.getLogger(__name__)
URL = "https://api.onesignal.com/notifications"


def habilitado() -> bool:
    return bool(settings.ONESIGNAL_APP_ID and settings.ONESIGNAL_REST_API_KEY)


def enviar(usuario_id: int, titulo: str, mensaje: str) -> bool:
    if not habilitado():
        return False
    cuerpo = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "target_channel": "push",
        "include_aliases": {"external_id": [str(usuario_id)]},
        "headings": {"es": titulo, "en": titulo},
        "contents": {"es": mensaje, "en": mensaje},
    }
    req = urllib.request.Request(
        URL, data=json.dumps(cuerpo).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Key {settings.ONESIGNAL_REST_API_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.ONESIGNAL_TIMEOUT_SECONDS) as r:
            return 200 <= r.status < 300
    except Exception as e:  # sin conexión, clave inválida, etc.
        log.warning("No se pudo enviar el push a %s: %s", usuario_id, e)
        return False
