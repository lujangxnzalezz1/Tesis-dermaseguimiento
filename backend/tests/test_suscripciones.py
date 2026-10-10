import re
import time
from datetime import timedelta
from decimal import Decimal

import pytest

from core.tiempo import ahora
from models.suscripcion import Comprobante, HistorialSuscripcion, Notificacion, Pago, Suscripcion
from services.letras import monto_en_letras
from tests.conftest import firmar_evento, pagar, webhook


def susc(client, h):
    return client.get("/suscripcion", headers=h).json()


def test_planes_publicos_coinciden_con_las_reglas(client):
    r = client.get("/planes")  # sin autenticación
    assert r.status_code == 200
    planes = {p["codigo"]: p for p in r.json()["planes"]}
    assert set(planes) == {"gratuito", "premium_mensual", "premium_anual"}
    m = planes["premium_mensual"]
    assert Decimal(m["precio"]) == 149000 and m["moneda"] == "PYG" and m["periodicidad"] == "mensual" and m["duracion_dias"] == 30
    assert m["funcionalidades"] and m["limites"] and m["condiciones"] and m["incluye_procesamiento"]
    assert Decimal(planes["premium_anual"]["precio"]) == 1190000 and planes["gratuito"]["incluye_procesamiento"] is False


def test_usuario_nuevo_inicia_con_periodo_de_prueba(client, doc):
    s = susc(client, doc)
    assert s["estado"] == "prueba" and s["es_prueba"] and s["dias_restantes"] in (13, 14)
    assert s["funciones_avanzadas"] is True and s["categoria"] == "activa"


def test_pago_aprobado_activa_suscripcion_y_emite_comprobante(client, doc, db):
    info, r = pagar(client, doc)
    assert r.json() == {"procesado": True, "estado": "aprobado"}
    s = susc(client, doc)
    assert s["estado"] == "activa" and not s["es_prueba"] and s["plan"]["codigo"] == "premium_mensual" and s["dias_restantes"] in (29, 30)
    comps = client.get("/comprobantes", headers=doc).json()["items"]
    assert len(comps) == 1
    c = comps[0]
    assert re.fullmatch(r"REC-\d{6}", c["numero"]) and Decimal(c["monto"]) == 149000 and c["moneda"] == "PYG"
    assert c["monto_letras"] == "Ciento cuarenta y nueve mil guaraníes" and "no constituye factura" in c["leyenda"].lower()
    assert c["pagador_email"] == "doc1@example.com" and c["referencia"].startswith("SBX-") and c["forma_pago"]
    pagos = client.get("/pagos", headers=doc).json()["items"]
    assert pagos[0]["estado"] == "aprobado" and pagos[0]["comprobante_numero"] == c["numero"]
    eventos = [h.evento for h in db.query(HistorialSuscripcion).order_by(HistorialSuscripcion.id)]
    assert eventos == ["alta", "alta"]  # alta de prueba + alta paga
    assert client.get(f"/pagos/{info['pago_id']}", headers=doc).json()["estado"] == "aprobado"


def test_webhook_duplicado_no_se_procesa_dos_veces(client, doc):
    info, r1 = pagar(client, doc)
    ref = info["url_pago"].rsplit("/", 1)[-1]
    r2 = webhook(client, ref, "aprobado", info["monto"], evento_id="otro-evento")
    r3 = webhook(client, ref, "aprobado", info["monto"], evento_id="ev1")
    assert r2.status_code == r3.status_code == 200 and r2.json()["procesado"] is False
    assert len(client.get("/comprobantes", headers=doc).json()["items"]) == 1
    # un evento contradictorio posterior tampoco cambia el estado final
    webhook(client, ref, "rechazado", info["monto"], evento_id="ev9")
    assert client.get("/pagos", headers=doc).json()["items"][0]["estado"] == "aprobado"


def test_webhook_rechaza_notificaciones_no_autenticas(client, doc):
    info = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    ref = info["url_pago"].rsplit("/", 1)[-1]
    evento = {"evento_id": "e", "referencia": ref, "estado": "aprobado", "monto": info["monto"], "moneda": "PYG"}
    cuerpo, cab = firmar_evento(evento)
    assert client.post("/webhooks/pago", content=cuerpo).status_code == 401                              # sin firma
    assert client.post("/webhooks/pago", content=cuerpo, headers={**cab, "X-Pasarela-Firma": "0" * 64}).status_code == 401  # firma falsa
    cuerpo2, cab2 = firmar_evento(evento, ts=time.time() - 3600)
    assert client.post("/webhooks/pago", content=cuerpo2, headers=cab2).status_code == 401                # repetición antigua
    adulterado = cuerpo.replace(b"aprobado", b"aprobadO")
    assert client.post("/webhooks/pago", content=adulterado, headers=cab).status_code == 401              # cuerpo modificado
    assert susc(client, doc)["estado"] == "prueba"                                                          # nada cambió
    assert client.get("/comprobantes", headers=doc).json()["total"] == 0


def test_webhook_valida_monto_y_referencia(client, doc):
    info = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    ref = info["url_pago"].rsplit("/", 1)[-1]
    assert webhook(client, ref, "aprobado", "0.01").status_code == 400
    assert webhook(client, ref, "aprobado", info["monto"], moneda="USD").status_code == 400
    assert webhook(client, "SBX-INEXISTENTE", "aprobado", "149000").status_code == 404
    assert webhook(client, ref, "raro", info["monto"]).status_code == 400
    assert client.post("/webhooks/pago", content=b"no json", headers=firmar_evento({})[1]).status_code in (400, 401)


@pytest.mark.parametrize("estado", ["rechazado", "cancelado"])
def test_pago_rechazado_o_cancelado_no_activa(client, doc, estado):
    info, r = pagar(client, doc, estado=estado)
    assert r.json()["estado"] == estado
    assert susc(client, doc)["estado"] == "prueba"
    assert client.get("/comprobantes", headers=doc).json()["total"] == 0
    # puede reintentar
    info2, r2 = pagar(client, doc, evento_id="ev2")
    assert r2.json()["estado"] == "aprobado" and susc(client, doc)["estado"] == "activa"


def test_pago_pendiente_no_cambia_nada_y_no_permite_duplicar(client, doc):
    info = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    ref = info["url_pago"].rsplit("/", 1)[-1]
    assert webhook(client, ref, "pendiente", info["monto"]).json()["procesado"] is False
    assert client.get(f"/pagos/{info['pago_id']}", headers=doc).json()["estado"] == "pendiente"
    assert client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).status_code == 409
    assert susc(client, doc)["pago_pendiente"] is True


def test_no_se_puede_ver_el_pago_de_otro(client, doc, doc2):
    info = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    assert client.get(f"/pagos/{info['pago_id']}", headers=doc2).status_code == 404


def test_plan_inexistente(client, doc):
    assert client.post("/suscripcion/checkout", json={"plan_codigo": "platino"}, headers=doc).status_code == 404
    assert client.post("/suscripcion/checkout", json={}, headers=doc).status_code == 422


def test_renovacion_extiende_desde_el_vencimiento(client, doc, db):
    pagar(client, doc)
    antes = db.query(Suscripcion).one().fecha_vencimiento
    info, r = pagar(client, doc, evento_id="ev2")
    assert info["tipo"] == "renovacion" and r.json()["estado"] == "aprobado"
    db.expire_all()
    despues = db.query(Suscripcion).one().fecha_vencimiento
    assert despues - antes == timedelta(days=30)
    assert "renovacion" in [h.evento for h in db.query(HistorialSuscripcion)]


def test_mejora_de_plan_con_credito_proporcional(client, doc, db):
    pagar(client, doc)  # mensual
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() + timedelta(days=15)})
    db.commit()
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_anual"}, headers=doc).json()
    assert r["tipo"] == "cambio_plan"
    esperado = Decimal(1190000) - Decimal(149000) * Decimal(15) / Decimal(30)          # Gs. 1.115.500 (aprox.)
    assert abs(Decimal(r["monto"]) - esperado) <= 100 and Decimal(r["credito"]) > 74000
    assert Decimal(r["monto"]) == Decimal(r["monto"]).to_integral_value()               # el guaraní no tiene centavos
    ref = r["url_pago"].rsplit("/", 1)[-1]
    assert webhook(client, ref, "aprobado", r["monto"]).status_code == 200
    s = susc(client, doc)
    assert s["plan"]["codigo"] == "premium_anual" and s["dias_restantes"] in (364, 365)
    assert "cambio_plan" in [h.evento for h in db.query(HistorialSuscripcion)]


def test_baja_de_plan_se_programa_sin_cobro(client, doc, db):
    pagar(client, doc, plan="premium_anual")
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    assert r["accion"] == "programada" and "reembolso" in r["mensaje"].lower()
    assert susc(client, doc)["plan_siguiente"]["codigo"] == "premium_mensual"
    assert susc(client, doc)["plan"]["codigo"] == "premium_anual"       # conserva el plan hasta terminar
    assert db.query(Pago).count() == 1


def test_bajar_al_gratuito_se_aplica_al_vencer(client, doc, db):
    pagar(client, doc)
    assert client.post("/suscripcion/checkout", json={"plan_codigo": "gratuito"}, headers=doc).json()["accion"] == "programada"
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() - timedelta(minutes=1)})
    db.commit()
    s = susc(client, doc)
    assert s["plan"]["codigo"] == "gratuito" and s["estado"] == "activa" and s["funciones_avanzadas"] is False


def test_cancelacion_exige_confirmacion_y_conserva_acceso(client, doc):
    pagar(client, doc)
    assert client.post("/suscripcion/cancelar", json={"motivo": "Ya no la uso"}, headers=doc).status_code == 400
    assert client.post("/suscripcion/cancelar", json={"motivo": "", "confirmar": True}, headers=doc).status_code == 422
    r = client.post("/suscripcion/cancelar", json={"motivo": "Ya no la uso", "confirmar": True}, headers=doc)
    assert r.status_code == 200
    s = susc(client, doc)
    assert s["estado"] == "cancelada" and s["categoria"] == "cancelada" and s["funciones_avanzadas"] is True
    assert client.post("/suscripcion/cancelar", json={"motivo": "otra vez", "confirmar": True}, headers=doc).status_code == 409
    assert "cancelacion" in [h["evento"] for h in client.get("/suscripcion/historial", headers=doc).json()]


def test_no_se_cancela_el_plan_gratuito(client, doc, db):
    pagar(client, doc)
    client.post("/suscripcion/checkout", json={"plan_codigo": "gratuito"}, headers=doc)
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() - timedelta(minutes=1)})
    db.commit()
    assert client.post("/suscripcion/cancelar", json={"motivo": "quiero", "confirmar": True}, headers=doc).status_code == 409


def test_vencimiento_bloquea_lo_avanzado(client, doc, db):
    pagar(client, doc)
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() - timedelta(days=2)})
    db.commit()
    s = susc(client, doc)
    assert s["estado"] == "vencida" and s["funciones_avanzadas"] is False and s["dias_restantes"] == 0
    assert "vencimiento" in [h["evento"] for h in client.get("/suscripcion/historial", headers=doc).json()]


# ------------------------------------------------------------------ avisos (punto 13)
@pytest.mark.parametrize("dias,hito", [(6.5, 7), (2.5, 3), (0.5, 1)])
def test_avisos_anticipados_sin_repetirse(client, doc, db, dias, hito):
    pagar(client, doc)
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() + timedelta(days=dias)})
    db.commit()
    venc = lambda: [n for n in client.get("/notificaciones", headers=doc).json()["items"] if n["tipo"] == "vencimiento"]
    a = venc()
    assert len(a) == 1 and "vence en" in a[0]["mensaje"]
    assert len(venc()) == 1 == db.query(Notificacion).filter(Notificacion.tipo == "vencimiento").count()  # no se repite


def test_sin_aviso_si_falta_mucho_y_aviso_posterior_al_vencimiento(client, doc, db):
    pagar(client, doc)
    assert [n for n in client.get("/notificaciones", headers=doc).json()["items"] if n["tipo"] == "vencimiento"] == []
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() - timedelta(days=1)})
    db.commit()
    tipos = [n["tipo"] for n in client.get("/notificaciones", headers=doc).json()["items"]]
    assert "vencida" in tipos
    nid = client.get("/notificaciones", headers=doc).json()["items"][0]["id"]
    assert client.post(f"/notificaciones/{nid}/leida", headers=doc).status_code == 200


def test_avisos_por_correo_quedan_registrados(client, doc, db, monkeypatch):
    enviados = []
    monkeypatch.setattr("services.email_service.enviar", lambda d, dest, codigo, ctx: enviados.append(codigo) or True)
    pagar(client, doc)
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() + timedelta(days=2.5)})
    db.commit()
    client.get("/notificaciones", headers=doc)
    assert "aviso_vencimiento" in enviados
    assert db.query(Notificacion).filter(Notificacion.tipo == "vencimiento").one().correo_enviado is True


# ------------------------------------------------------------------ comprobantes (punto 36)
def test_comprobante_pdf_y_reimpresion(client, doc, doc2, db):
    pagar(client, doc)
    cid = client.get("/comprobantes", headers=doc).json()["items"][0]["id"]
    r = client.get(f"/comprobantes/{cid}/pdf", headers=doc)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"
    client.get(f"/comprobantes/{cid}/pdf", headers=doc)
    assert client.get(f"/comprobantes/{cid}", headers=doc).json()["estado"] == "reimpreso"
    assert client.get(f"/comprobantes/{cid}", headers=doc2).status_code == 404
    assert client.get(f"/comprobantes/{cid}/pdf", headers=doc2).status_code == 404


def test_numeracion_correlativa_sin_duplicados(client, doc, doc2):
    pagar(client, doc)
    pagar(client, doc2)
    pagar(client, doc, evento_id="e3")
    numeros = [c["numero"] for h in (doc, doc2) for c in client.get("/comprobantes", headers=h).json()["items"]]
    assert len(numeros) == len(set(numeros)) == 3


def test_comprobante_se_puede_anular_solo_por_admin(client, doc, admin):
    pagar(client, doc)
    cid = client.get("/comprobantes", headers=doc).json()["items"][0]["id"]
    assert client.post(f"/admin/comprobantes/{cid}/anular", json={"motivo": "Error de carga", "confirmar": True}, headers=doc).status_code == 403
    assert client.post(f"/admin/comprobantes/{cid}/anular", json={"motivo": "Error de carga"}, headers=admin).status_code == 400
    assert client.post(f"/admin/comprobantes/{cid}/anular", json={"motivo": "Error de carga", "confirmar": True}, headers=admin).status_code == 200
    assert client.get(f"/comprobantes/{cid}", headers=doc).json()["estado"] == "anulado"
    assert client.post(f"/admin/comprobantes/{cid}/anular", json={"motivo": "Error de carga", "confirmar": True}, headers=admin).status_code == 409


def test_monto_en_letras_y_formato_en_guaranies():
    from services.letras import formato_monto
    assert monto_en_letras(Decimal("149000"), "PYG") == "Ciento cuarenta y nueve mil guaraníes"
    assert monto_en_letras(Decimal("1190000"), "PYG") == "Un millón ciento noventa mil guaraníes"
    assert monto_en_letras(Decimal("21000"), "PYG") == "Veintiún mil guaraníes"
    assert formato_monto(Decimal("1190000.00"), "PYG") == "Gs. 1.190.000" and formato_monto(Decimal("9.99"), "USD") == "USD 9,99"


def test_monto_en_letras():
    assert monto_en_letras(Decimal("9.99")) == "Nueve dólares estadounidenses con 99/100"
    assert monto_en_letras(Decimal("79.99")) == "Setenta y nueve dólares estadounidenses con 99/100"
    assert monto_en_letras(Decimal("1.00")) == "Uno dólar estadounidense con 00/100".replace("Uno", "Uno")
    assert monto_en_letras(Decimal("100.50")) == "Cien dólares estadounidenses con 50/100"
    assert monto_en_letras(Decimal("1234.00")).startswith("Mil doscientos treinta y cuatro")
    assert monto_en_letras(Decimal("21.00")).startswith("Veintiún") or monto_en_letras(Decimal("21.00")).startswith("Veintiuno")


# ------------------------------------------------------------------ exportación (punto 23)
def test_exportar_pagos_csv(client, doc):
    pagar(client, doc)
    r = client.get("/pagos.csv?estado=aprobado", headers=doc)
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")
    t = r.content.decode("utf-8-sig").splitlines()
    assert t[0].startswith("Reporte;Historial de pagos") and t[1].startswith("Generado") and "estado=aprobado" in t[2]
    assert "Fecha;Referencia;Tipo;Estado;Monto;Moneda" in t
    assert any(l.endswith(";aprobado;149000;PYG") for l in t) and "Total aprobado;149000" in t and "Total de registros;1" in t
    assert 'filename="pagos_' in r.headers["content-disposition"]
    p = client.get("/pagos.csv?decimal=punto", headers=doc).content.decode("utf-8-sig")
    assert ";149000;PYG" in p
    assert client.get("/pagos.csv?estado=inventado", headers=doc).status_code == 422
