"""Verificación de CAPTCHA en el servidor, independiente del proveedor.

Proveedores soportados (CAPTCHA_PROVIDER): Cloudflare Turnstile, hCaptcha y Google reCAPTCHA
(v2 o v3). Los tres usan el mismo protocolo: POST con secret + response (+ remoteip) y una
respuesta JSON con `success`. Si CAPTCHA_SECRET está vacío el CAPTCHA queda desactivado (pruebas
y desarrollo local). Los fallos se registran en la auditoría."""
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from core.config import settings
from core.security import ip_cliente

log = logging.getLogger("captcha")

URLS_VERIFICACION = {
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "hcaptcha": "https://api.hcaptcha.com/siteverify",
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
}
CABECERA_APP_NATIVA = "app-nativa"  # valor de la cabecera X-Cliente que envía la app nativa


def activo() -> bool:
    return bool(settings.CAPTCHA_SECRET)


def proveedor() -> str:
    p = settings.CAPTCHA_PROVIDER.strip().lower()
    return p if p in URLS_VERIFICACION else "turnstile"


def configuracion_publica() -> dict:
    """Lo que la app necesita para dibujar el widget. Nunca incluye la clave secreta."""
    return {
        "activo": activo() and bool(settings.CAPTCHA_SITE_KEY),
        "proveedor": proveedor(),
        "site_key": settings.CAPTCHA_SITE_KEY if activo() else "",
        "eximir_app_nativa": settings.CAPTCHA_EXIMIR_APP_NATIVA,
    }


def _consultar_proveedor(token: str, ip: Optional[str]) -> dict:
    url = settings.CAPTCHA_VERIFY_URL or URLS_VERIFICACION[proveedor()]
    datos = urllib.parse.urlencode({"secret": settings.CAPTCHA_SECRET, "response": token, "remoteip": ip or ""}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=datos), timeout=5) as r:
        return json.loads(r.read())


def _fallo(db, request, accion: str, detalle: str, status: int, mensaje: str) -> HTTPException:
    if db is not None:
        from services import auditoria_service as audit  # importación diferida: evita un ciclo

        audit.registrar_fallo(db, request, None, "seguridad", "captcha", f"{accion}: {detalle}")
    return HTTPException(status, mensaje)


def verificar_captcha(token: Optional[str], request: Request, db: Optional[Session] = None, accion: str = "") -> None:
    if not activo():
        return
    if settings.CAPTCHA_EXIMIR_APP_NATIVA and request.headers.get("x-cliente") == CABECERA_APP_NATIVA:
        return
    if not token:
        raise _fallo(db, request, accion, "sin token", 400, "Completá la verificación de seguridad (CAPTCHA) para continuar.")
    try:
        respuesta = _consultar_proveedor(token, ip_cliente(request))
    except Exception:
        log.exception("No se pudo verificar el CAPTCHA")
        raise _fallo(db, request, accion, "proveedor no disponible", 503,
                     "No pudimos verificar la seguridad de tu solicitud. Intentá de nuevo en unos minutos.")
    ok = respuesta.get("success") is True
    puntaje = respuesta.get("score")  # solo reCAPTCHA v3
    if ok and isinstance(puntaje, (int, float)) and puntaje < settings.CAPTCHA_PUNTAJE_MINIMO:
        ok = False
    if not ok:
        codigos = ",".join(respuesta.get("error-codes") or [])[:100]
        raise _fallo(db, request, accion, f"token rechazado {codigos}".strip(), 400,
                     "La verificación de seguridad (CAPTCHA) falló. Intentá de nuevo.")
