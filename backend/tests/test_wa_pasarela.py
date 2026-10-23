"""Pasarela: el webhook sandbox no existe con AdamsPay y nunca decide pagos de otro proveedor;
estados de la deuda de AdamsPay y verificación del pago consultando al proveedor (simulado)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import settings
from models.auditoria import Auditoria
from models.suscripcion import Comprobante, Pago, Suscripcion
from routers import pasarela_sandbox
from services import pasarela as pas
from tests.conftest import webhook


# ------------------------------------------------------------------ webhook sandbox

def test_con_adamspay_no_se_registran_las_rutas_sandbox(monkeypatch):
    monkeypatch.setattr(settings, "PASARELA", "adamspay")
    sin_sandbox = FastAPI()
    assert pasarela_sandbox.incluir_en(sin_sandbox) is False
    monkeypatch.setattr(settings, "PASARELA", "sandbox")  # aunque luego cambie la configuración, las rutas no existen
    with TestClient(sin_sandbox) as c:
        assert c.post("/webhooks/pago", content=b"{}").status_code == 404
        assert c.get("/pasarela-sandbox/checkout/SBX-1").status_code == 404
        assert "/webhooks/pago" not in c.get("/openapi.json").json()["paths"]

    con_sandbox = FastAPI()
    assert pasarela_sandbox.incluir_en(con_sandbox) is True
    with TestClient(con_sandbox) as c:
        assert c.post("/webhooks/pago", content=b"{}").status_code == 401  # existe: exige la firma


def test_webhook_firmado_no_responde_en_modo_adamspay(client, doc, monkeypatch):
    info = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    ref = info["url_pago"].rsplit("/", 1)[-1]
    monkeypatch.setattr(settings, "PASARELA", "adamspay")
    assert webhook(client, ref, "aprobado", info["monto"]).status_code == 404
    assert client.get(f"/pasarela-sandbox/checkout/{ref}").status_code == 404


def _pago_adamspay(db, usuario_id=1, monto="149000", plan_id=2):
    susc = db.query(Suscripcion).filter(Suscripcion.usuario_id == usuario_id).one()
    pago = Pago(usuario_id=usuario_id, suscripcion_id=susc.id, plan_id=plan_id, tipo="alta", monto=Decimal(monto), moneda="PYG",
                proveedor="adamspay", referencia_externa="DS-PRUEBA1")
    db.add(pago)
    db.commit()
    return pago


def test_webhook_sandbox_rechaza_pagos_de_otro_proveedor(client, doc, db):
    client.get("/suscripcion", headers=doc)
    pago = _pago_adamspay(db)
    r = webhook(client, "DS-PRUEBA1", "aprobado", "149000")  # firma válida con el secreto local
    assert r.status_code == 409
    db.expire_all()
    assert db.get(Pago, pago.id).estado == "pendiente" and db.query(Comprobante).count() == 0
    assert db.query(Auditoria).filter(Auditoria.modulo == "pagos", Auditoria.resultado == "fallo").count() >= 1


# ------------------------------------------------------------------ estados de la deuda

def _deuda(pago="pending", objeto="active", fin=None, **extra):
    fin = fin or (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S")
    return {"payStatus": {"status": pago}, "objStatus": {"status": objeto}, "validPeriod": {"end": fin},
            "amount": {"value": "149000", "currency": "PYG"}, **extra}


@pytest.mark.parametrize("deuda, esperado", [
    (_deuda("paid", "success"), "aprobado"),
    (_deuda(objeto="canceled"), "cancelado"),
    (_deuda(objeto="voided"), "cancelado"),
    (_deuda(objeto="expired"), "vencido"),
    (_deuda(fin="2020-01-01T00:00:00"), "vencido"),          # fuera del período de validez
    (_deuda(fin="2020-01-01T00:00:00Z"), "vencido"),
    (_deuda(), "pendiente"),
    (_deuda(objeto="alert"), "pendiente"),
])
def test_estado_de_la_deuda(deuda, esperado):
    assert pas.estado_de_deuda(deuda) == esperado


def test_vigencia_y_tiempo_de_espera_configurables(monkeypatch):
    import io
    import json

    monkeypatch.setattr(settings, "ADAMSPAY_API_KEY", "clave-prueba")
    monkeypatch.setattr(settings, "ADAMSPAY_VIGENCIA_HORAS", 3)
    monkeypatch.setattr(settings, "ADAMSPAY_TIMEOUT_SEGUNDOS", 7)
    visto = {}

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def falso(req, timeout):
        visto["timeout"], visto["deuda"] = timeout, json.loads(req.data)["debt"]
        return Resp(json.dumps({"debt": {"payUrl": "https://x"}}).encode())

    monkeypatch.setattr(pas.urllib.request, "urlopen", falso)
    pas.PasarelaAdamsPay().crear_operacion(Decimal("149000"), "PYG", "x")
    inicio = datetime.fromisoformat(visto["deuda"]["validPeriod"]["start"])
    fin = datetime.fromisoformat(visto["deuda"]["validPeriod"]["end"])
    assert visto["timeout"] == 7 and fin - inicio == timedelta(hours=3)


# ------------------------------------------------------------------ verificar_pago_externo

@pytest.fixture
def adamspay(monkeypatch):
    """AdamsPay simulado: `estado['deuda']` es lo que devolverá la consulta (o una excepción)."""
    monkeypatch.setattr(settings, "PASARELA", "adamspay")
    monkeypatch.setattr(settings, "ADAMSPAY_API_KEY", "clave-prueba")
    estado = {"n": 0, "deuda": _deuda()}

    def crear(self, monto, moneda, descripcion):
        estado["n"] += 1
        return f"DS-{estado['n']}", f"https://staging.adamspay.com/pay/{estado['n']}"

    def llamar(self, metodo, ruta, cuerpo=None):
        if isinstance(estado["deuda"], Exception):
            raise estado["deuda"]
        return {"debt": estado["deuda"]}

    monkeypatch.setattr(pas.PasarelaAdamsPay, "crear_operacion", crear)
    monkeypatch.setattr(pas.PasarelaAdamsPay, "_llamar", llamar)
    return estado


def _checkout(client, h, plan="premium_mensual"):
    return client.post("/suscripcion/checkout", json={"plan_codigo": plan}, headers=h)


def test_adamspay_pagado_aprueba_activa_y_audita(client, doc, db, adamspay):
    info = _checkout(client, doc).json()
    assert client.get(f"/pagos/{info['pago_id']}", headers=doc).json()["estado"] == "pendiente"
    adamspay["deuda"] = _deuda("paid", "success", refs={"txList": [
        {"txId": "TX-997", "type": "debtDocPay", "objStatus": {"status": "failed"}, "method": "card"},
        {"txId": "TX-998", "type": "debtDocPay", "objStatus": {"status": "success"}, "method": "card"}]})
    r = client.get(f"/pagos/{info['pago_id']}", headers=doc).json()
    assert r["estado"] == "aprobado" and r["comprobante_id"]
    pago = db.get(Pago, info["pago_id"])
    assert pago.transaccion_id == "TX-998" and pago.forma_pago == "AdamsPay — Tarjeta de crédito/débito"
    assert client.get("/suscripcion", headers=doc).json()["estado"] == "activa"
    aud = db.query(Auditoria).filter(Auditoria.accion == "pago_aprobado", Auditoria.entidad_id == str(pago.id)).one()
    assert aud.usuario_id == pago.usuario_id and "AdamsPay" in aud.detalle
    # Consultar de nuevo no vuelve a aprobar ni emite otro comprobante
    client.get(f"/pagos/{info['pago_id']}", headers=doc)
    assert db.query(Comprobante).count() == 1


def test_adamspay_monto_distinto_no_aprueba(client, doc, db, adamspay):
    info = _checkout(client, doc).json()
    adamspay["deuda"] = {**_deuda("paid", "success"), "amount": {"value": "1000", "currency": "PYG"}}
    assert client.get(f"/pagos/{info['pago_id']}", headers=doc).json()["estado"] == "pendiente"
    assert db.query(Comprobante).count() == 0
    assert db.query(Auditoria).filter(Auditoria.accion == "verificar_pago", Auditoria.resultado == "fallo").count() == 1


@pytest.mark.parametrize("deuda, estado", [(_deuda(objeto="expired"), "vencido"), (_deuda(objeto="canceled"), "cancelado"),
                                           (_deuda(fin="2020-01-01T00:00:00"), "vencido")])
def test_adamspay_vencida_o_cancelada_permite_un_nuevo_checkout(client, doc, db, adamspay, deuda, estado):
    info = _checkout(client, doc).json()
    assert _checkout(client, doc).status_code == 409          # mientras la deuda sigue vigente, bloquea
    adamspay["deuda"] = deuda
    nuevo = _checkout(client, doc)                              # al consultar, la deuda ya no sirve: se cierra
    assert nuevo.status_code == 200, nuevo.text
    assert db.get(Pago, info["pago_id"]).estado == estado
    assert nuevo.json()["pago_id"] != info["pago_id"]


def test_adamspay_sin_conexion_es_un_error_controlado(client, doc, db, adamspay):
    info = _checkout(client, doc).json()
    adamspay["deuda"] = pas.ErrorPasarela("No se pudo conectar con AdamsPay: timeout")
    r = client.get(f"/pagos/{info['pago_id']}", headers=doc)
    assert r.status_code == 503 and "pendiente" in r.json()["detail"]
    assert db.get(Pago, info["pago_id"]).estado == "pendiente"
    assert _checkout(client, doc).status_code == 409           # sin confirmar con AdamsPay, no se duplica el cobro


def test_adamspay_respuesta_rara_es_error_controlado(monkeypatch):
    monkeypatch.setattr(settings, "ADAMSPAY_API_KEY", "clave-prueba")
    monkeypatch.setattr(pas.PasarelaAdamsPay, "_llamar", lambda self, m, r, c=None: {"otra": "cosa"})
    with pytest.raises(pas.ErrorPasarela):
        pas.PasarelaAdamsPay().consultar("DS-1")
