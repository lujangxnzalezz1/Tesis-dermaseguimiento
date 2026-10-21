"""Comprobantes: desglose con IVA incluido y crédito, datos del pagador, logo opcional, reimpresión sin
cambiar el estado, inmutabilidad del anulado, reemisión con número nuevo y enlace de descarga (app nativa)."""
from datetime import timedelta
from decimal import Decimal

import pytest

from core.config import settings
from core.tiempo import ahora
from models.suscripcion import Comprobante, Suscripcion
from services import suscripcion_service as svc
from services.comprobante_pdf import generar_pdf
from tests.conftest import pagar, webhook


@pytest.fixture
def textos_pdf(monkeypatch):
    """Captura el texto que se escribe en el PDF (el contenido va comprimido dentro del archivo)."""
    from reportlab.pdfgen import canvas
    escritos = []
    original = canvas.Canvas.drawString

    def capturar(self, x, y, texto, *a, **k):
        escritos.append(texto)
        return original(self, x, y, texto, *a, **k)

    monkeypatch.setattr(canvas.Canvas, "drawString", capturar)
    return escritos


def _primer_comprobante(client, h):
    return client.get("/comprobantes", headers=h).json()["items"][0]


def test_desglose_iva_incluido_y_datos_del_pagador(client, doc, db):
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual", "documento": "4567890", "telefono": "0981 123456"}, headers=doc).json()
    webhook(client, r["url_pago"].rsplit("/", 1)[-1], "aprobado", r["monto"])
    c = _primer_comprobante(client, doc)
    assert Decimal(c["monto"]) == 149000 and Decimal(c["subtotal"]) == 149000 and Decimal(c["credito"]) == 0
    assert Decimal(c["iva"]) == 13545                                     # 149.000 / 11, IVA incluido
    assert c["pagador_documento"] == "4567890" and c["pagador_telefono"] == "0981 123456"


def test_desglose_con_credito_proporcional(client, doc, db):
    pagar(client, doc)
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() + timedelta(days=15)})
    db.commit()
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_anual"}, headers=doc).json()
    webhook(client, r["url_pago"].rsplit("/", 1)[-1], "aprobado", r["monto"], evento_id="ev2")
    c = _primer_comprobante(client, doc)
    assert Decimal(c["credito"]) == Decimal(r["credito"]) and Decimal(c["subtotal"]) == Decimal(c["monto"]) + Decimal(c["credito"])
    assert Decimal(c["iva"]) == (Decimal(c["monto"]) / 11).quantize(Decimal("1"))


def test_pdf_incluye_desglose_leyenda_y_marca_de_reimpresion(client, doc, textos_pdf):
    pagar(client, doc)
    cid = _primer_comprobante(client, doc)["id"]
    assert client.get(f"/comprobantes/{cid}/pdf", headers=doc).status_code == 200
    primero = "\n".join(textos_pdf)
    assert "Subtotal: Gs. 149.000" in primero and "IVA 10 % incluido: Gs. 13.545" in primero and "Total recibido: Gs. 149.000" in primero
    assert "No constituye factura legal" in primero.replace("\n", "") and "RUC / CI: No informado" in primero
    assert "REIMPRESIÓN" not in primero and "Crédito" not in primero
    textos_pdf.clear()
    client.get(f"/comprobantes/{cid}/pdf", headers=doc)
    assert any("Estado: EMITIDO (REIMPRESIÓN)" in t for t in textos_pdf) and any("Reimpresión n.º 1" in t for t in textos_pdf)


def test_logo_opcional(client, doc, db, monkeypatch, tmp_path):
    import cv2
    import numpy as np

    pagar(client, doc)
    comp = db.query(Comprobante).one()
    monkeypatch.setattr(settings, "EMISOR_LOGO_RUTA", str(tmp_path / "no_existe.png"))
    sin_logo = generar_pdf(comp)                                          # ruta inexistente: se omite sin error
    logo = tmp_path / "logo.png"
    cv2.imwrite(str(logo), np.full((40, 120, 3), 90, dtype=np.uint8))
    monkeypatch.setattr(settings, "EMISOR_LOGO_RUTA", str(logo))
    con_logo = generar_pdf(comp)
    assert sin_logo.startswith(b"%PDF") and con_logo.startswith(b"%PDF") and b"/Subtype /Image" in con_logo and b"/Subtype /Image" not in sin_logo
    (tmp_path / "danado.png").write_bytes(b"no es una imagen")
    monkeypatch.setattr(settings, "EMISOR_LOGO_RUTA", str(tmp_path / "danado.png"))
    assert generar_pdf(comp).startswith(b"%PDF")


def test_anulado_es_inmutable_y_se_reemite_con_otro_numero(client, doc, admin, db):
    pagar(client, doc)
    viejo = _primer_comprobante(client, doc)
    # Solo se reemite un comprobante anulado
    assert client.post(f"/admin/comprobantes/{viejo['id']}/reemitir", headers=admin).status_code == 409
    assert client.post(f"/admin/comprobantes/{viejo['id']}/anular", json={"motivo": "Error en los datos", "confirmar": True}, headers=admin).status_code == 200
    assert client.post(f"/admin/comprobantes/{viejo['id']}/reemitir", headers=doc).status_code == 403
    r = client.post(f"/admin/comprobantes/{viejo['id']}/reemitir", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["numero"] != viejo["numero"]
    assert client.post(f"/admin/comprobantes/{viejo['id']}/reemitir", headers=admin).status_code == 409   # ya hay uno vigente

    items = client.get("/comprobantes", headers=doc).json()["items"]
    assert {c["estado"] for c in items} == {"emitido", "anulado"}
    anulado = next(c for c in items if c["estado"] == "anulado")
    assert anulado["numero"] == viejo["numero"] and anulado["monto"] == viejo["monto"]
    pago = client.get("/pagos", headers=doc).json()["items"][0]
    assert pago["comprobante_numero"] == r.json()["numero"]                 # el pago muestra el vigente

    # El anulado se puede descargar, pero no cambia (ni siquiera el contador)
    assert client.get(f"/comprobantes/{viejo['id']}/pdf", headers=doc).status_code == 200
    db.expire_all()
    c = db.get(Comprobante, viejo["id"])
    assert c.reimpresiones == anulado["reimpresiones"]
    c.monto = Decimal("1")
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()
    c = db.get(Comprobante, viejo["id"])
    c.estado = "emitido"
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()


def test_comprobante_emitido_no_admite_cambios_de_contenido(client, doc, db):
    pagar(client, doc)
    c = db.query(Comprobante).one()
    c.concepto = "Otra cosa"
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()
    c = db.query(Comprobante).one()
    db.delete(c)
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()


def test_un_pago_tiene_un_solo_comprobante_vigente(client, doc, db):
    pagar(client, doc)
    pago_id = db.query(Comprobante).one().pago_id
    with pytest.raises(Exception):
        svc._emitir_comprobante(db, db.get(svc.Pago, pago_id), db.get(svc.Usuario, 1), "x", None)
        db.commit()
    db.rollback()


def test_enlace_de_descarga_para_la_app_nativa(client, doc, doc2):
    pagar(client, doc)
    cid = _primer_comprobante(client, doc)["id"]
    assert client.post(f"/comprobantes/{cid}/enlace", headers=doc2).status_code == 404
    url = client.post(f"/comprobantes/{cid}/enlace", headers=doc).json()["url"]
    ruta = "/" + url.split("/", 3)[3]
    r = client.get(ruta)                                                    # sin cabecera de sesión
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-disposition"].startswith("inline")
    token = ruta.rsplit("/", 1)[-1]
    assert client.get("/suscripcion", headers={"Authorization": f"Bearer {token}"}).status_code == 401  # no sirve como sesión
    sesion = doc["Authorization"].split()[1]
    assert client.get(f"/comprobantes/descarga/{sesion}").status_code == 401                         # la sesión no sirve como enlace
    assert client.get("/comprobantes/descarga/basura").status_code == 401
