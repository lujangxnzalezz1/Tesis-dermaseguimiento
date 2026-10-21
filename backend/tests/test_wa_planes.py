"""Planes: cotización previa al pago, historial, baja programada a otro plan pago y edición por el administrador."""
from datetime import timedelta
from decimal import Decimal

from core.tiempo import ahora
from models.auditoria import Auditoria
from models.suscripcion import Pago, Plan, Suscripcion
from tests.conftest import pagar, webhook


def susc(client, h):
    return client.get("/suscripcion", headers=h).json()


def test_cotizacion_muestra_monto_y_credito_sin_crear_pago(client, doc, db):
    pagar(client, doc)  # mensual
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() + timedelta(days=15)})
    db.commit()
    c = client.get("/suscripcion/cotizacion", params={"plan_codigo": "premium_anual"}, headers=doc)
    assert c.status_code == 200
    c = c.json()
    assert c["accion"] == "cobrar" and c["tipo"] == "cambio_plan" and Decimal(c["precio"]) == 1190000
    assert Decimal(c["credito"]) > 74000 and Decimal(c["monto"]) == Decimal(c["precio"]) - Decimal(c["credito"])
    assert Decimal(c["iva_incluido"]) == (Decimal(c["monto"]) / 11).quantize(Decimal("1"))
    assert db.query(Pago).count() == 1                                             # solo el pago anterior
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_anual"}, headers=doc).json()
    assert r["monto"] == c["monto"] and r["credito"] == c["credito"]                # la pasarela cobra lo que se mostró
    assert client.get("/suscripcion/cotizacion", params={"plan_codigo": "premium_anual"}).status_code == 401
    assert client.get("/suscripcion/cotizacion", params={"plan_codigo": "no_existe"}, headers=doc).status_code == 404


def test_historial_con_nombres_de_plan(client, doc):
    pagar(client, doc)
    h = client.get("/suscripcion/historial", headers=doc).json()
    assert h[0]["evento"] == "alta" and h[0]["plan_nuevo"] == "Premium mensual"


def test_baja_de_anual_a_mensual_se_aplica_al_vencer_y_queda_pendiente_de_pago(client, doc, db):
    pagar(client, doc, plan="premium_anual")
    assert client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()["accion"] == "programada"
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() - timedelta(minutes=1)})
    db.commit()
    s = susc(client, doc)
    assert s["plan"]["codigo"] == "premium_mensual" and s["plan_siguiente"] is None
    assert s["estado"] == "vencida" and s["funciones_avanzadas"] is False
    eventos = [h["evento"] for h in client.get("/suscripcion/historial", headers=doc).json()]
    assert "cambio_plan" in eventos and "vencimiento" in eventos
    # Pagar el mensual lo activa por 30 días
    info, r = pagar(client, doc, evento_id="ev2")
    assert info["tipo"] == "alta" and Decimal(info["monto"]) == 149000 and r.json()["estado"] == "aprobado"
    s = susc(client, doc)
    assert s["estado"] == "activa" and s["dias_restantes"] in (29, 30)


def test_baja_programada_no_se_aplica_si_se_cancelo(client, doc, db):
    pagar(client, doc, plan="premium_anual")
    client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc)
    client.post("/suscripcion/cancelar", json={"motivo": "Ya no la uso", "confirmar": True}, headers=doc)
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() - timedelta(minutes=1)})
    db.commit()
    s = susc(client, doc)
    assert s["plan"]["codigo"] == "premium_anual" and s["estado"] == "vencida"


def test_checkout_guarda_documento_y_telefono_para_el_recibo(client, doc, db):
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual", "documento": "80012345-6", "telefono": "+595 981 123456"},
                    headers=doc)
    assert r.status_code == 200
    pago = db.get(Pago, r.json()["pago_id"])
    assert pago.pagador_documento == "80012345-6" and pago.pagador_telefono == "+595 981 123456"
    assert client.post("/suscripcion/checkout", json={"plan_codigo": "premium_anual", "documento": "abc<script>"}, headers=doc).status_code == 422
    assert client.post("/suscripcion/checkout", json={"plan_codigo": "premium_anual", "telefono": "llamame"}, headers=doc).status_code == 422


# ------------------------------------------------------------------ administración de planes

def test_admin_lista_y_edita_planes_con_auditoria(client, admin, db):
    r = client.get("/admin/planes", headers=admin)
    assert r.status_code == 200 and {p["codigo"] for p in r.json()["planes"]} == {"gratuito", "premium_mensual", "premium_anual"}
    cambios = {"precio": 159000, "funcionalidades": ["Todo lo del plan Gratuito", "Comparación de fotografías"],
               "limites": [], "condiciones": "Gs. 159.000 cada 30 días, IVA incluido."}
    r = client.patch("/admin/planes/premium_mensual", json=cambios, headers=admin)
    assert r.status_code == 200, r.text
    publico = {p["codigo"]: p for p in client.get("/planes").json()["planes"]}["premium_mensual"]
    assert Decimal(publico["precio"]) == 159000 and publico["limites"] == [] and len(publico["funcionalidades"]) == 2
    aud = db.query(Auditoria).filter(Auditoria.modulo == "planes", Auditoria.accion == "editar").one()
    assert "149000" in aud.datos_antes and "159000" in aud.datos_despues


def test_admin_desactiva_un_plan_y_deja_de_ofrecerse(client, admin, doc):
    assert client.patch("/admin/planes/premium_anual", json={"activo": False}, headers=admin).status_code == 200
    assert "premium_anual" not in {p["codigo"] for p in client.get("/planes").json()["planes"]}
    assert "premium_anual" in {p["codigo"] for p in client.get("/admin/planes", headers=admin).json()["planes"]}
    assert client.post("/suscripcion/checkout", json={"plan_codigo": "premium_anual"}, headers=doc).status_code == 404


def test_dermatologo_no_puede_editar_planes(client, doc):
    assert client.get("/admin/planes", headers=doc).status_code == 403
    assert client.patch("/admin/planes/premium_mensual", json={"precio": 1}, headers=doc).status_code == 403
    assert client.get("/admin/planes").status_code == 401


def test_validaciones_de_la_edicion_de_planes(client, admin, db):
    def editar(codigo, datos):
        return client.patch(f"/admin/planes/{codigo}", json=datos, headers=admin).status_code

    assert editar("premium_mensual", {}) == 400
    assert editar("no_existe", {"precio": 1}) == 404
    assert editar("premium_mensual", {"precio": -5}) == 422
    assert editar("premium_mensual", {"precio": 0}) == 422                 # plan pago sin precio
    assert editar("premium_mensual", {"precio": 149000.5}) == 422          # el guaraní no tiene centavos
    assert editar("gratuito", {"precio": 1000}) == 422
    assert editar("gratuito", {"activo": False}) == 409
    assert editar("premium_mensual", {"funcionalidades": []}) == 422
    assert editar("premium_mensual", {"funcionalidades": ["A", "A"]}) == 422
    assert editar("premium_mensual", {"funcionalidades": ["<b>x</b>"]}) == 422
    assert editar("premium_mensual", {"condiciones": ""}) == 422
    assert editar("premium_mensual", {"funcionalidades": ["x"] * 21}) == 422
    assert editar("premium_anual", {"activo": False}) == 200
    assert editar("premium_mensual", {"activo": False}) == 409             # queda al menos un Premium activo
    assert db.query(Plan).filter(Plan.codigo == "premium_mensual").one().precio == 149000


def test_precio_nuevo_no_cambia_pagos_ya_iniciados(client, doc, admin):
    info = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    client.patch("/admin/planes/premium_mensual", json={"precio": 199000}, headers=admin)
    ref = info["url_pago"].rsplit("/", 1)[-1]
    assert webhook(client, ref, "aprobado", info["monto"]).json()["estado"] == "aprobado"
