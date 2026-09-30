"""RF-16: análisis colorimétrico de la región periorbital (ojeras) con los puntos faciales."""
import os

import cv2
import numpy as np
import pytest

from services.periorbital import REGIONES, _mascara, analizar_periorbital
from services.procesamiento_imagenes import detectar_landmarks
from tests.conftest import crear_paciente

ROSTRO = cv2.imread(os.path.join(os.path.dirname(__file__), "datos", "rostro_sintetico.jpg"))
PUNTOS = detectar_landmarks(ROSTRO)
ALTO, ANCHO = ROSTRO.shape[:2]


def test_regiones_quedan_debajo_de_los_ojos():
    for lado, ojo_ext, nariz in (("derecho", 33, 1), ("izquierdo", 263, 1)):
        ys, xs = np.where(_mascara(PUNTOS, REGIONES[lado]["ojera"], ALTO, ANCHO))
        assert PUNTOS[ojo_ext][1] - 15 < ys.mean() < PUNTOS[nariz][1]  # entre el ojo y la punta de la nariz
    # cada ojera queda del lado de su ojo
    cx = lambda lado: np.where(_mascara(PUNTOS, REGIONES[lado]["ojera"], ALTO, ANCHO))[1].mean()  # noqa: E731
    assert (cx("derecho") < ANCHO / 2) != (cx("izquierdo") < ANCHO / 2)


def test_valores_razonables_en_el_rostro_de_prueba():
    r = analizar_periorbital(ROSTRO, PUNTOS)
    for lado in ("derecho", "izquierdo"):
        assert 0 < r[lado]["ojera_lab"][0] < 100 and r[lado]["contraste_L"] > 0  # la ojera es más oscura que la mejilla
    assert r["contraste_L_promedio"] == pytest.approx((r["derecho"]["contraste_L"] + r["izquierdo"]["contraste_L"]) / 2, abs=0.01)


def test_detecta_ojeras_mas_marcadas():
    oscurecida = ROSTRO.copy()
    for lado in REGIONES:
        m = _mascara(PUNTOS, REGIONES[lado]["ojera"], ALTO, ANCHO)
        oscurecida[m] = (oscurecida[m] * 0.8).astype(np.uint8)
    antes, despues = analizar_periorbital(ROSTRO, PUNTOS), analizar_periorbital(oscurecida, PUNTOS)
    assert despues["contraste_L_promedio"] > antes["contraste_L_promedio"] + 5


def test_contraste_menos_sensible_a_la_luz_que_el_color_absoluto():
    """Argumento de diseño: con otra iluminación el L* absoluto de la ojera cambia mucho más que el contraste."""
    oscura = (ROSTRO * 0.8).astype(np.uint8)
    a, b = analizar_periorbital(ROSTRO, PUNTOS), analizar_periorbital(oscura, PUNTOS)
    cambio_absoluto = abs(a["derecho"]["ojera_lab"][0] - b["derecho"]["ojera_lab"][0])
    cambio_contraste = abs(a["derecho"]["contraste_L"] - b["derecho"]["contraste_L"])
    assert cambio_contraste < cambio_absoluto / 2


def test_seguimiento_incluye_ojeras(client, doc):
    p = crear_paciente(client, doc)
    jpg = lambda i: cv2.imencode(".jpg", i)[1].tobytes()  # noqa: E731
    m = cv2.getRotationMatrix2D((ANCHO / 2, ALTO / 2), 4, 1.08)
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, headers=doc, files={
        "imagen_referencia": ("r.jpg", jpg(ROSTRO), "image/jpeg"),
        "imagen_nueva": ("n.jpg", jpg(cv2.warpAffine(ROSTRO, m, (ANCHO, ALTO), borderMode=cv2.BORDER_REPLICATE)), "image/jpeg")})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["ojeras_contraste_referencia"] > 0 and s["ojeras_contraste_nueva"] > 0
    assert abs(s["ojeras_contraste_nueva"] - s["ojeras_contraste_referencia"]) < 3  # misma cara, solo movida
    assert set(s["ojeras_detalle"]) == {"referencia", "nueva"}
    assert client.get(s["url_imagen_periorbital"], headers=doc).status_code == 200
    csv = client.get(f"/pacientes/{p['id']}/reporte.csv", headers=doc).content.decode("utf-8-sig")
    assert "Contraste ojeras (L*)" in csv and "SSIM alineada" in csv
