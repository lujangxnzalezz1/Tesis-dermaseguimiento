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
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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


class ErrorPasarela(Exception):
    pass


class PasarelaAdamsPay:
    """AdamsPay (Paraguay): cada pago es una «deuda» con una URL de pago propia.
    El estado se consulta al API con la apikey; no depende de un webhook público."""
    nombre = "adamspay"

    def _llamar(self, metodo: str, ruta: str, cuerpo: Optional[dict] = None) -> dict:
        req = urllib.request.Request(
            settings.ADAMSPAY_API_URL.rstrip("/") + ruta, method=metodo,
            data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
            headers={"apikey": settings.ADAMSPAY_API_KEY, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise ErrorPasarela(f"AdamsPay respondió {e.code}: {e.read().decode()[:300]}")
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErrorPasarela(f"No se pudo conectar con AdamsPay: {e}")

    def crear_operacion(self, pago_monto, moneda: str, descripcion: str) -> tuple[str, str]:
        referencia = "DS-" + uuid.uuid4().hex[:20].upper()
        inicio = datetime.now(timezone.utc).replace(microsecond=0)
        fin = inicio + timedelta(days=1)
        deuda = {
            "docId": referencia, "label": descripcion,
            "amount": {"currency": moneda, "value": str(int(pago_monto))},
            "validPeriod": {"start": inicio.strftime("%Y-%m-%dT%H:%M:%S"), "end": fin.strftime("%Y-%m-%dT%H:%M:%S")},
        }
        r = self._llamar("POST", "/debts", {"debt": deuda})
        try:
            return referencia, r["debt"]["payUrl"]
        except (KeyError, TypeError):
            raise ErrorPasarela(f"Respuesta inesperada de AdamsPay: {str(r)[:300]}")

    def consultar(self, referencia: str) -> dict:
        """Devuelve {'pagado': bool, 'monto': Decimal, 'moneda': str} según el estado de la deuda."""
        d = self._llamar("GET", f"/debts/{referencia}")["debt"]
        return {"pagado": d["payStatus"]["status"] == "paid",
                "monto": Decimal(str(d["amount"]["value"])), "moneda": d["amount"]["currency"]}


def obtener_pasarela():
    if settings.PASARELA == "adamspay":
        if not settings.ADAMSPAY_API_KEY:
            raise RuntimeError("Falta ADAMSPAY_API_KEY para usar la pasarela AdamsPay.")
        return PasarelaAdamsPay()
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
