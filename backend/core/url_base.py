"""Dirección pública del servidor para armar enlaces (correo de confirmación, página de pago).

Se toma de la solicitud en curso, así funciona en cualquier red (localhost en la Mac, IP de la red
desde el celular). Solo se confía en hosts locales o de red privada: con cualquier otro valor del
encabezado Host se usa BASE_URL, para que nadie pueda desviar un enlace a un sitio ajeno.
"""
import re
from contextvars import ContextVar

from core.config import settings

_actual: ContextVar[str | None] = ContextVar("url_base", default=None)
_HOST_CONFIABLE = re.compile(
    r"^(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d{1,5})?$"
)


def fijar_desde_solicitud(esquema: str, host: str | None) -> None:
    if host and _HOST_CONFIABLE.match(host) and esquema in ("http", "https"):
        _actual.set(f"{esquema}://{host}")
    else:
        _actual.set(None)


def url_base() -> str:
    return (_actual.get() or settings.BASE_URL).rstrip("/")
