"""Textura: líneas/arrugas, poros y brillo de la zona T, comparados entre consultas."""
import os

import cv2
import numpy as np

from services import textura as T
from services.procesamiento_imagenes import detectar_landmarks
from tests.conftest import crear_paciente

ROSTRO = cv2.imread(os.path.join(os.path.dirname(__file__), "datos", "rostro_sintetico.jpg"))
PUNTOS = detectar_landmarks(ROSTRO)
ALTO, ANCHO = ROSTRO.shape[:2]


def _con_lineas(img, puntos):
    con = img.copy()
    y0 = int(0.35 * np.mean([puntos[i][1] for i in (67, 297, 10)]) + 0.65 * np.mean([puntos[i][1] for i in (105, 334)]))
    for k in range(3):
        cv2.line(con, (int(puntos[67][0]) + 20, y0 + 14 * k), (int(puntos[297][0]) - 20, y0 + 14 * k + 3), (110, 85, 70), 2, cv2.LINE_AA)
    return cv2.addWeighted(img, 0.45, con, 0.55, 0)


def test_escala_con_la_distancia_entre_pupilas():
    e = T.escala_px_por_mm(PUNTOS)
    assert 3 < e < 10  # foto de prueba de ≈ 1 MP


def test_frente_sin_lineas_y_con_lineas():
    antes = T.analizar(ROSTRO, PUNTOS)["lineas_por_zona"]["frente"]
    despues = T.analizar(_con_lineas(ROSTRO, PUNTOS), PUNTOS)["lineas_por_zona"]["frente"]
    assert antes < 1 and despues > antes + 5  # las cejas y el borde del rostro no cuentan como líneas


def test_lineas_poco_sensibles_a_la_luz():
    con = _con_lineas(ROSTRO, PUNTOS)
    a, b = T.analizar(con, PUNTOS)["lineas_mm_cm2"], T.analizar((con * 0.75).astype(np.uint8), PUNTOS)["lineas_mm_cm2"]
    assert abs(a - b) < 1.5


def test_poros_solo_con_detalle_suficiente():
    assert T.analizar(ROSTRO, PUNTOS)["poros_cm2"] is None  # foto chica: no se inventa un valor
    grande = cv2.resize(ROSTRO, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    p = detectar_landmarks(grande)
    e = T.escala_px_por_mm(p)
    mej = T.zonas(p, *grande.shape[:2])["mejillas"]
    ys, xs = np.where(mej)
    idx = np.random.default_rng(1).choice(len(xs), 300, replace=False)
    con = grande.copy()
    for i in idx:
        cv2.circle(con, (int(xs[i]), int(ys[i])), int(0.12 * e), (90, 70, 60), -1, cv2.LINE_AA)
    con = cv2.addWeighted(grande, 0.6, con, 0.4, 0)
    esperado = 300 / (mej.sum() / (e * 10) ** 2)
    medido = T.analizar(con, p)["poros_cm2"]
    assert abs(medido - esperado) < 0.15 * esperado
    assert T.analizar(grande, p)["poros_cm2"] < 3


def test_brillo_en_la_zona_t():
    m = np.zeros((ALTO, ANCHO), np.float32)
    cv2.ellipse(m, tuple(int(v) for v in PUNTOS[195]), (14, 40), 0, 0, 360, 1, -1)
    m = cv2.GaussianBlur(m, (0, 0), 5)[..., None]
    con = (ROSTRO * (1 - m) + np.array([250, 250, 252]) * m).astype(np.uint8)
    assert T.analizar(ROSTRO, PUNTOS)["brillo_pct"] < 0.5 and T.analizar(con, PUNTOS)["brillo_pct"] > 1.5


def test_seguimiento_textura_recomendaciones_y_pdf(client, doc, doc2):
    p = crear_paciente(client, doc)
    jpg = lambda i: cv2.imencode(".jpg", i)[1].tobytes()  # noqa: E731
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, headers=doc, files={
        "imagen_referencia": ("r.jpg", jpg(ROSTRO), "image/jpeg"), "imagen_nueva": ("n.jpg", jpg(_con_lineas(ROSTRO, PUNTOS)), "image/jpeg")})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["textura_nueva"]["lineas_mm_cm2"] > s["textura_referencia"]["lineas_mm_cm2"]
    assert "_mascara_lineas" not in s["textura_nueva"] and client.get(s["url_imagen_textura"], headers=doc).status_code == 200
    assert any("líneas de expresión" in f for f in s["interpretacion"]["resumen"])

    url = f"/seguimientos/{s['id']}/recomendaciones"
    assert client.put(url, json={"texto": "Protector solar FPS 50 cada 3 horas."}, headers=doc2).status_code == 404
    assert client.put(url, json={"texto": "x" * 2001}, headers=doc).status_code == 422
    g = client.put(url, json={"texto": "  Protector solar FPS 50 cada 3 horas.\nControl en 30 días.  "}, headers=doc)
    assert g.status_code == 200 and g.json()["recomendaciones"].startswith("Protector solar")
    pdf = client.get(f"/seguimientos/{s['id']}/informe.pdf", headers=doc)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.put(url, json={"texto": "   "}, headers=doc).json()["recomendaciones"] is None
    csv = client.get(f"/pacientes/{p['id']}/reporte.csv", headers=doc).content.decode("utf-8-sig")
    assert "Líneas (mm/cm²)" in csv and "Brillo zona T (%)" in csv
