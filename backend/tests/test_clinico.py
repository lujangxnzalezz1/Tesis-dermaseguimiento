"""Valoración clínica (IGA, mMASI, mediciones con equipo), foto UV (porfirinas) y plantillas de indicaciones."""
import os

import cv2
import numpy as np

from services import porfirinas as P
from services.clinico import puntaje_mmasi
from services.procesamiento_imagenes import detectar_landmarks
from tests.conftest import crear_paciente

ROSTRO = cv2.imread(os.path.join(os.path.dirname(__file__), "datos", "rostro_sintetico.jpg"))
jpg = lambda i: cv2.imencode(".jpg", i)[1].tobytes()  # noqa: E731


def _foto_uv(puntos_rojos=0):
    g = cv2.cvtColor(ROSTRO, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    uv = np.stack([g * 170 + 20, g * 60 + 10, g * 120 + 25], -1).clip(0, 255).astype(np.uint8)  # violeta, como con lámpara de Wood
    if puntos_rojos:
        cx, cy = detectar_landmarks(uv)[1]
        rng = np.random.default_rng(3)
        for _ in range(puntos_rojos):
            cv2.circle(uv, (int(cx + rng.integers(-200, 200)), int(cy + rng.integers(-280, 180))), 3, (40, 140, 255), -1, cv2.LINE_AA)
    return uv


def _seguimiento(client, doc):
    p = crear_paciente(client, doc)
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, headers=doc, files={
        "imagen_referencia": ("r.jpg", jpg(ROSTRO), "image/jpeg"),
        "imagen_nueva": ("n.jpg", jpg(cv2.convertScaleAbs(ROSTRO, alpha=1.0, beta=3)), "image/jpeg")})
    assert r.status_code == 201, r.text
    return p, r.json()


def test_mmasi_formula():
    reg = lambda a, d: {"area": a, "oscuridad": d}  # noqa: E731
    assert puntaje_mmasi({"frente": reg(6, 4), "malar_derecha": reg(6, 4), "malar_izquierda": reg(6, 4), "menton": reg(6, 4)}) == 24.0
    assert puntaje_mmasi({"frente": reg(3, 2), "malar_derecha": reg(2, 2), "malar_izquierda": reg(0, 0), "menton": reg(1, 3)}) == 3.3


def test_porfirinas_en_foto_uv():
    assert P.analizar(_foto_uv(), detectar_landmarks(_foto_uv()))["cantidad"] == 0
    con = _foto_uv(40)
    r = P.analizar(con, detectar_landmarks(con))
    assert 36 <= r["cantidad"] <= 40 and r["por_cm2"] > 0 and r["rostro_detectado"]


def test_valoracion_clinica(client, doc, doc2):
    _, s = _seguimiento(client, doc)
    url = f"/seguimientos/{s['id']}/valoracion"
    masi = {k: {"area": 2, "oscuridad": 1} for k in ("frente", "malar_derecha", "malar_izquierda", "menton")}
    assert client.put(url, json={"iga": 5}, headers=doc).status_code == 422
    assert client.put(url, json={"ph": 12}, headers=doc).status_code == 422
    assert client.put(url, json={"masi": {**masi, "frente": {"area": 7, "oscuridad": 1}}}, headers=doc).status_code == 422
    assert client.put(url, json={"iga": 2}, headers=doc2).status_code == 404
    r = client.put(url, json={"iga": 2, "masi": masi, "humedad": 45.5, "ph": 5.4, "equipo": " Corneometer CM 825 "}, headers=doc)
    assert r.status_code == 200, r.text
    vc = r.json()["valoracion_clinica"]
    assert vc["iga_texto"] == "Leve" and vc["mmasi"] == 2.0 and vc["equipo"] == "Corneometer CM 825" and "firmeza" not in vc
    pdf = client.get(f"/seguimientos/{s['id']}/informe.pdf", headers=doc)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.put(url, json={"equipo": "   "}, headers=doc).json()["valoracion_clinica"] is None  # nada cargado = se borra


def test_foto_uv_en_el_seguimiento(client, doc, doc2):
    p, s = _seguimiento(client, doc)
    url = f"/seguimientos/{s['id']}/foto-uv"
    assert client.post(url, headers=doc2, files={"imagen": ("uv.jpg", jpg(_foto_uv(20)), "image/jpeg")}).status_code == 404
    r = client.post(url, headers=doc, files={"imagen": ("uv.jpg", jpg(_foto_uv(20)), "image/jpeg")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert 16 <= d["porfirinas"]["cantidad"] <= 20 and "_centros" not in d["porfirinas"]
    assert client.get(d["url_imagen_uv_analisis"], headers=doc).status_code == 200
    anterior = d["url_imagen_uv"]
    d2 = client.post(url, headers=doc, files={"imagen": ("uv.jpg", jpg(_foto_uv(0)), "image/jpeg")}).json()
    assert d2["porfirinas"]["cantidad"] == 0 and client.get(anterior, headers=doc).status_code == 404  # la anterior se reemplaza
    csv = client.get(f"/pacientes/{p['id']}/reporte.csv", headers=doc).content.decode("utf-8-sig")
    assert "Porfirinas (por cm²)" in csv and "mMASI" in csv


def test_plantillas_de_indicaciones(client, doc, doc2):
    r = client.post("/plantillas-indicaciones", json={"titulo": "Acné leve", "texto": "Limpieza suave dos veces por día."}, headers=doc)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.post("/plantillas-indicaciones", json={"titulo": "", "texto": "x"}, headers=doc).status_code == 422
    assert [x["titulo"] for x in client.get("/plantillas-indicaciones", headers=doc).json()] == ["Acné leve"]
    assert client.get("/plantillas-indicaciones", headers=doc2).json() == []  # cada profesional ve solo las suyas
    assert client.delete(f"/plantillas-indicaciones/{pid}", headers=doc2).status_code == 404
    assert client.delete(f"/plantillas-indicaciones/{pid}", headers=doc).status_code == 204
    assert client.get("/plantillas-indicaciones", headers=doc).json() == []
