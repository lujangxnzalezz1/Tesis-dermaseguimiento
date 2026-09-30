"""RF-03: guía y control de calidad de la captura. Usa un rostro sintético real para MediaPipe."""
import os

import cv2
import numpy as np
import pytest

from core.config import settings
from services.calidad_captura import evaluar_captura
from tests.conftest import crear_paciente

ROSTRO = cv2.imread(os.path.join(os.path.dirname(__file__), "datos", "rostro_sintetico.jpg"))
ALTO, ANCHO = ROSTRO.shape[:2]


def girar(img, angulo, escala=1.0):
    m = cv2.getRotationMatrix2D((ANCHO / 2, ALTO / 2), angulo, escala)
    return cv2.warpAffine(img, m, (ANCHO, ALTO), borderMode=cv2.BORDER_REPLICATE)


def niveles(res):
    return {c["codigo"]: c["nivel"] for c in res["controles"]}


def jpg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def test_foto_correcta_es_apta():
    res = evaluar_captura(ROSTRO)
    assert res["apta"] is True and all(n == "ok" for n in niveles(res).values())


@pytest.mark.parametrize("nombre,img,codigo,nivel", [
    ("sin rostro", np.full_like(ROSTRO, 180), "rostro", "error"),
    ("inclinada", girar(ROSTRO, 15, 1.2), "inclinacion", "error"),
    ("lejos", girar(ROSTRO, 0, 0.45), "distancia", "error"),
    ("oscura", (ROSTRO * 0.35).astype(np.uint8), "luz", "error"),
    ("sobreexpuesta", np.clip(ROSTRO.astype(int) * 2.2, 0, 255).astype(np.uint8), "luz", "error"),
    ("borrosa", cv2.GaussianBlur(ROSTRO, (0, 0), 6), "nitidez", "aviso"),
    ("descentrada", np.roll(ROSTRO, int(ANCHO * 0.25), axis=1), "centrado", "aviso"),
])
def test_detecta_problemas_de_toma(nombre, img, codigo, nivel):
    res = evaluar_captura(img)
    assert niveles(res)[codigo] == nivel, (nombre, res["controles"])
    assert res["apta"] is (nivel != "error")
    assert all(c["mensaje"] for c in res["controles"])  # siempre dice qué corregir


def test_compara_con_la_consulta_anterior():
    distinta_luz = evaluar_captura((ROSTRO * 0.75).astype(np.uint8), ROSTRO)
    assert niveles(distinta_luz)["igual_luz"] == "aviso" and "más oscura" in next(
        c["mensaje"] for c in distinta_luz["controles"] if c["codigo"] == "igual_luz")
    mas_cerca = evaluar_captura(girar(ROSTRO, 0, 1.25), ROSTRO)
    assert niveles(mas_cerca)["igual_distancia"] == "aviso"
    igual = evaluar_captura(ROSTRO, ROSTRO)
    assert niveles(igual)["igual_luz"] == niveles(igual)["igual_distancia"] == "ok"


def test_umbrales_configurables(monkeypatch):
    monkeypatch.setattr(settings, "CAPTURA_INCLINACION_MAX_GRADOS", 20.0)
    assert niveles(evaluar_captura(girar(ROSTRO, 15, 1.2)))["inclinacion"] == "ok"


# ------------------------------------------------------------------ endpoints
def test_verificar_captura_endpoint(client, doc):
    r = client.post("/verificar-captura", files={"imagen": ("f.jpg", jpg(ROSTRO), "image/jpeg")}, headers=doc)
    assert r.status_code == 200 and r.json()["apta"] is True
    r = client.post("/verificar-captura", files={"imagen": ("f.jpg", jpg((ROSTRO * 0.3).astype(np.uint8)), "image/jpeg")}, headers=doc)
    assert r.json()["apta"] is False
    assert client.post("/verificar-captura", files={"imagen": ("f.jpg", jpg(ROSTRO), "image/jpeg")}).status_code == 401
    assert client.post("/verificar-captura", files={"imagen": ("x.pdf", b"%PDF", "application/pdf")}, headers=doc).status_code == 400


def test_flujo_con_referencia_de_primera_consulta(client, doc, doc2):
    p = crear_paciente(client, doc)
    assert client.get(f"/pacientes/{p['id']}/referencia", headers=doc).json()["existe"] is False
    # primera consulta: sin foto de referencia no se puede
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])},
                    files={"imagen_nueva": ("n.jpg", jpg(ROSTRO), "image/jpeg")}, headers=doc)
    assert r.status_code == 400 and "primera consulta" in r.json()["detail"]
    # consulta 1 con ambas fotos (reales, sin simular la detección)
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, headers=doc, files={
        "imagen_referencia": ("r.jpg", jpg(ROSTRO), "image/jpeg"),
        "imagen_nueva": ("n.jpg", jpg(girar(ROSTRO, 4, 1.1)), "image/jpeg")})
    assert r.status_code == 201, r.text
    ref = client.get(f"/pacientes/{p['id']}/referencia", headers=doc).json()
    assert ref["existe"] and client.get(ref["url"], headers=doc).status_code == 200
    assert client.get(f"/pacientes/{p['id']}/referencia", headers=doc2).status_code == 404
    # consulta 2: solo la foto nueva; la referencia sale de la primera consulta
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])},
                    files={"imagen_nueva": ("n.jpg", jpg(girar(ROSTRO, -3, 1.05)), "image/jpeg")}, headers=doc)
    assert r.status_code == 201 and r.json()["landmarks_nueva"] == 478
    # y la verificación compara contra esa referencia
    v = client.post("/verificar-captura", data={"paciente_id": str(p["id"])},
                    files={"imagen": ("f.jpg", jpg((ROSTRO * 0.75).astype(np.uint8)), "image/jpeg")}, headers=doc).json()
    assert v["comparacion"] is not None and niveles(v)["igual_luz"] == "aviso"
