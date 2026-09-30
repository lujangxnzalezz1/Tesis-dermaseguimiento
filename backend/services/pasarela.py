"""Pasarela de pago (punto 14).

`PasarelaSandbox` es una pasarela de pruebas AUTÓNOMA: expone su propia página de
checkout y avisa el resultado al sistema mediante un webhook firmado con HMAC-SHA256,
igual que lo haría una pasarela real. El sistema NO cambia el estado del pago con un
botón propio: solo reacciona a eventos firmados y validados.

Para usar una pasarela real en modo sandbox (Pagopar, Bancard vPOS, Stripe test, etc.)
se implementa una clase con la misma interfaz y se elige con PASARELA=<nombre>.
"""
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Optional

from core.config import settings
from core.url_base import url_base


class ErrorFirma(Exception):
    pass


def firmar(cuerpo: bytes, timestamp: str, secreto: Optional[str] = None) -> str:
    secreto = secreto or settings.PASARELA_WEBHOOK_SECRET
    return hmac.new(secreto.encode(), timestamp.encode() + b"." + cuerpo, hashlib.sha256).hexdigest()


def verificar_firma(cuerpo: bytes, timestamp: Optional[str], firma: Optional[str]) -> None:
    if not timestamp or not firma:
        raise ErrorFirma("Faltan los encabezados de firma.")
    try:
        antiguedad = abs(time.time() - float(timestamp))
    except ValueError:
        raise ErrorFirma("Marca de tiempo inválida.")
    if antiguedad > settings.PASARELA_WEBHOOK_TOLERANCIA_SEGUNDOS:
        raise ErrorFirma("La notificación es demasiado antigua (posible repetición).")
    if not hmac.compare_digest(firma, firmar(cuerpo, timestamp)):
        raise ErrorFirma("Firma inválida.")


class PasarelaSandbox:
    nombre = "sandbox"

    def crear_operacion(self, pago_monto, moneda: str, descripcion: str) -> tuple[str, str]:
        """Devuelve (referencia_externa, url_de_pago)."""
        referencia = "SBX-" + uuid.uuid4().hex[:20].upper()
        return referencia, f"{url_base()}/pasarela-sandbox/checkout/{referencia}"


def obtener_pasarela() -> PasarelaSandbox:
    if settings.PASARELA == "sandbox":
        return PasarelaSandbox()
    raise RuntimeError(f"Pasarela «{settings.PASARELA}» no implementada.")


def enviar_webhook(evento: dict) -> int:
    """Lo usa la pasarela sandbox para notificar al sistema. Devuelve el código HTTP."""
    cuerpo = json.dumps(evento).encode()
    ts = str(int(time.time()))
    req = urllib.request.Request(
        f"{settings.BASE_URL.rstrip('/')}/webhooks/pago",  # dirección interna: el servidor se avisa a sí mismo
        data=cuerpo,
        method="POST",
        headers={"Content-Type": "application/json", "X-Pasarela-Timestamp": ts, "X-Pasarela-Firma": firmar(cuerpo, ts)},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
