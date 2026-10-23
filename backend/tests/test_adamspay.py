"""Pasarela AdamsPay: crear la deuda y aprobar el pago solo cuando AdamsPay la informa pagada con el monto correcto."""
import io
import json
from pathlib import Path
from decimal import Decimal

from core.config import settings
from services import pasarela as pas


class Resp(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_crea_la_deuda_y_devuelve_la_url(monkeypatch):
    monkeypatch.setattr(settings, "ADAMSPAY_API_KEY", "clave-prueba")
    enviado = {}

    def falso(req, timeout):
        enviado["url"], enviado["cuerpo"], enviado["apikey"] = req.full_url, json.loads(req.data), req.headers["Apikey"]
        return Resp(json.dumps({"debt": {"payUrl": "https://staging.adamspay.com/pay/x"}}).encode())

    monkeypatch.setattr(pas.urllib.request, "urlopen", falso)
    ref, url = pas.PasarelaAdamsPay().crear_operacion(Decimal("149000"), "PYG", "Suscripción Premium")
    assert url == "https://staging.adamspay.com/pay/x"
    assert enviado["url"].endswith("/debts") and enviado["apikey"] == "clave-prueba"
    assert enviado["cuerpo"]["debt"]["docId"] == ref
    assert enviado["cuerpo"]["debt"]["amount"] == {"currency": "PYG", "value": "149000"}


def test_consulta_el_estado(monkeypatch):
    monkeypatch.setattr(settings, "ADAMSPAY_API_KEY", "clave-prueba")
    deuda = {"debt": {"payStatus": {"status": "paid"}, "amount": {"value": "149000.0000", "currency": "PYG"}}}
    monkeypatch.setattr(pas.urllib.request, "urlopen", lambda req, timeout: Resp(json.dumps(deuda).encode()))
    estado = pas.PasarelaAdamsPay().consultar("DS-1")
    assert estado == {"estado": "aprobado", "pagado": True, "monto": Decimal("149000.0000"), "moneda": "PYG",
                      "transaccion_id": None, "forma_pago": None}


def test_sin_conexion_lanza_error_controlado(monkeypatch):
    monkeypatch.setattr(settings, "ADAMSPAY_API_KEY", "clave-prueba")

    def falla(*a, **k):
        raise pas.urllib.error.URLError("sin conexión")

    monkeypatch.setattr(pas.urllib.request, "urlopen", falla)
    try:
        pas.PasarelaAdamsPay().consultar("DS-1")
        assert False, "debía fallar"
    except pas.ErrorPasarela:
        pass


def test_respuesta_real_de_staging(monkeypatch):
    """Respuesta de GET /debts/{docId} obtenida del ambiente de pruebas de AdamsPay (pago con su simulador)."""
    real = json.loads((Path(__file__).parent / "datos" / "adamspay_deuda_pagada.json").read_text())
    monkeypatch.setattr(pas.PasarelaAdamsPay, "_llamar", lambda self, m, r, c=None: real)
    estado = pas.PasarelaAdamsPay().consultar("DS-39D8F93DD20841F8A274")
    assert estado["estado"] == "aprobado" and estado["pagado"] is True
    assert estado["monto"] == 149000 and estado["moneda"] == "PYG"
    assert estado["transaccion_id"] == "4408082008366"
    assert estado["forma_pago"] == "Simulador de AdamsPay (pruebas)"
