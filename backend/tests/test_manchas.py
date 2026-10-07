"""Manchas: zonas de la piel claramente más oscuras que su entorno, comparadas entre consultas."""
import os

import cv2
import numpy as np

from services.manchas import EXCLUIDAS, detectar_manchas, mascara_piel
from services.procesamiento_imagenes import detectar_landmarks
from tests.conftest import crear_paciente

ROSTRO = cv2.imread(os.path.join(os.path.dirname(__file__), "datos", "rostro_sintetico.jpg"))
PUNTOS = detectar_landmarks(ROSTRO)
ALTO, ANCHO = ROSTRO.shape[:2]
PIEL = mascara_piel(PUNTOS, ALTO, ANCHO)
MEJILLA = tuple(int(v) for v in PUNTOS[205])


def _oscurecer(img, centro, ejes, factor):
    m = np.zeros((ALTO, ANCHO), np.float32)
    cv2.ellipse(m, centro, ejes, 0, 0, 360, 1, -1)
    m = cv2.GaussianBlur(m, (0, 0), 6)[..., None]
    return (img * (1 - m * (1 - factor))).astype(np.uint8)


def test_mascara_excluye_ojos_labios_y_nariz():
    for idx, _ in EXCLUIDAS.values():
        for i in idx:
            x, y = PUNTOS[i]
            assert not PIEL[int(y), int(x)]
    assert PIEL[MEJILLA[1], MEJILLA[0]]  # la mejilla sí se analiza


def test_rostro_sin_manchas_casi_no_marca_nada():
    """Surcos, comisuras y sombras del relieve no deben contar como manchas."""
    assert detectar_manchas(ROSTRO, PIEL)["area_pct"] < 0.5


def test_detecta_manchas_agregadas():
    con = ROSTRO.copy()
    for dx, dy, r in ((0, 0, 22), (60, 40, 14), (-40, 70, 10)):
        con = _oscurecer(con, (MEJILLA[0] + dx, MEJILLA[1] + dy), (r, r), 0.75)
    antes, despues = detectar_manchas(ROSTRO, PIEL), detectar_manchas(con, PIEL)
    assert despues["cantidad"] >= 3
    assert despues["area_pct"] > antes["area_pct"] + 0.5


def test_detecta_un_parche_grande_tipo_melasma():
    parche = _oscurecer(ROSTRO, MEJILLA, (70, 45), 0.85)
    assert detectar_manchas(parche, PIEL)["area_pct"] > detectar_manchas(ROSTRO, PIEL)["area_pct"] + 2


def test_poco_sensible_a_la_iluminacion():
    """Argumento de diseño: el umbral es relativo a la piel de alrededor, así que la luz general casi no influye."""
    con = _oscurecer(ROSTRO, MEJILLA, (25, 25), 0.75)
    normal = detectar_manchas(con, PIEL)["area_pct"]
    oscura = detectar_manchas((con * 0.75).astype(np.uint8), PIEL)["area_pct"]
    gradiente = np.tile(np.linspace(1.0, 0.7, ANCHO, dtype=np.float32), (ALTO, 1))[..., None]
    lateral = detectar_manchas((con * gradiente).astype(np.uint8), PIEL)["area_pct"]
    assert abs(oscura - normal) < 0.3 and abs(lateral - normal) < 0.3


def test_seguimiento_incluye_manchas(client, doc):
    p = crear_paciente(client, doc)
    jpg = lambda i: cv2.imencode(".jpg", i)[1].tobytes()  # noqa: E731
    nueva = _oscurecer(ROSTRO, MEJILLA, (40, 30), 0.75)
    m = cv2.getRotationMatrix2D((ANCHO / 2, ALTO / 2), 3, 1.05)
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, headers=doc, files={
        "imagen_referencia": ("r.jpg", jpg(ROSTRO), "image/jpeg"),
        "imagen_nueva": ("n.jpg", jpg(cv2.warpAffine(nueva, m, (ANCHO, ALTO), borderMode=cv2.BORDER_REPLICATE)), "image/jpeg")})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["manchas_pct_nueva"] > s["manchas_pct_referencia"] + 0.5
    assert set(s["manchas_detalle"]) == {"referencia", "nueva"} and "mascara" not in s["manchas_detalle"]["nueva"]
    assert any("manchas" in f and "más superficie" in f for f in s["interpretacion"]["resumen"])
    assert client.get(s["url_imagen_manchas"], headers=doc).status_code == 200
    csv = client.get(f"/pacientes/{p['id']}/reporte.csv", headers=doc).content.decode("utf-8-sig")
    assert "Manchas (% de piel)" in csv
