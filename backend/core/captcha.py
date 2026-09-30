"""Verificación de CAPTCHA en el servidor (reCAPTCHA/Turnstile). Desactivado si CAPTCHA_SECRET está vacío."""
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

from fastapi import HTTPException

from core.config import settings

log = logging.getLogger("captcha")


def verificar_captcha(token: Optional[str], ip: Optional[str]) -> None:
    if not settings.CAPTCHA_SECRET:
        return
    if not token:
        raise HTTPException(400, "Completá la verificación de seguridad (CAPTCHA) para continuar.")
    datos = urllib.parse.urlencode({"secret": settings.CAPTCHA_SECRET, "response": token, "remoteip": ip or ""}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(settings.CAPTCHA_VERIFY_URL, data=datos), timeout=5) as r:
            ok = json.loads(r.read()).get("success", False)
    except Exception:
        log.exception("No se pudo verificar el CAPTCHA")
        raise HTTPException(503, "No pudimos verificar la seguridad de tu solicitud. Intentá de nuevo en unos minutos.")
    if not ok:
        raise HTTPException(400, "La verificación de seguridad (CAPTCHA) falló. Intentá de nuevo.")
