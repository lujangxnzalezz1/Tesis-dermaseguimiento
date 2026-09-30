"""RF-13 (SSIM), RF-14 (detección con YOLOv8) y RF-15 (comparación de lesiones entre consultas)."""
import os

import cv2
import numpy as np
import pytest

from services import deteccion_acne as da
from services.similitud import ssim
from tests.conftest import crear_paciente

ROSTRO = cv2.imread(os.path.join(os.path.dirname(__file__), "datos", "rostro_sintetico.jpg"))


def caja(x, y, lado=20, conf=0.9):
    return {"x1": x, "y1": y, "x2": x + lado, "y2": y + lado, "confianza": conf}


# ------------------------------------------------------------------ RF-15: comparación
def test_comparacion_persistentes_nuevas_y_resueltas():
    ref = [caja(100, 100), caja(300, 300), caja(500, 100)]
    nueva = [caja(103, 98), caja(302, 305), caja(700, 700)]  # dos iguales (leve corrimiento), una nueva
    c = da.comparar_lesiones(ref, nueva)
    assert len(c["persistentes"]) == 2 and len(c["nuevas"]) == 1 and len(c["resueltas"]) == 1
    assert c["nuevas"][0]["x1"] == 700 and c["resueltas"][0]["x1"] == 500


def test_comparacion_casos_limite():
    assert da.comparar_lesiones([], []) == {"persistentes": [], "nuevas": [], "resueltas": []}
    assert len(da.comparar_lesiones([], [caja(1, 1)])["nuevas"]) == 1
    assert len(da.comparar_lesiones([caja(1, 1)], [])["resueltas"]) == 1
    # una lesión de referencia no puede emparejarse con dos nuevas
    c = da.comparar_lesiones([caja(100, 100)], [caja(101, 101), caja(102, 102)])
    assert len(c["persistentes"]) == 1 and len(c["nuevas"]) == 1


def test_dibujo_no_modifica_la_original():
    img = np.zeros((200, 200, 3), np.uint8)
    out = da.dibujar_comparacion(img, {"persistentes": [caja(10, 10)], "nuevas": [caja(60, 60)], "resueltas": [caja(120, 120)]})
    assert img.sum() == 0 and out.sum() > 0


# ------------------------------------------------------------------ RF-14: lectura de la salida de YOLOv8
class RedFalsa:
    """Imita la salida ONNX de YOLOv8 (1, 4+clases, N) en coordenadas del lienzo de entrada."""
    def __init__(self, filas):
        self.salida = np.array(filas, np.float32).T[None]

    def setInput(self, _):
        pass

    def forward(self):
        return self.salida


@pytest.fixture
def red(monkeypatch):
    def instalar(filas):
        monkeypatch.setattr(da, "_red", RedFalsa(filas))
        monkeypatch.setattr(da, "_red_cargada", True)
    return instalar


def test_detecta_convierte_coordenadas_y_filtra(red, monkeypatch):
    monkeypatch.setattr(da.settings, "ACNE_IMGSZ", 1000)
    monkeypatch.setattr(da.settings, "ACNE_CONFIANZA_MIN", 0.3)
    # Imagen 500x1000 (ancho x alto) -> escala 1.0, relleno horizontal de 250 px
    img = np.zeros((1000, 500, 3), np.uint8)
    red([[350, 200, 20, 20, 0.9], [352, 201, 22, 20, 0.8], [600, 600, 10, 10, 0.1]])  # duplicado + baja confianza
    r = da.detectar_lesiones(img)
    assert len(r) == 1 and r[0]["x1"] == 90 and r[0]["y1"] == 190 and r[0]["confianza"] == 0.9


def test_descarta_lesiones_fuera_del_rostro(red, monkeypatch):
    monkeypatch.setattr(da.settings, "ACNE_IMGSZ", 100)
    img = np.zeros((100, 100, 3), np.uint8)
    mascara = np.zeros((100, 100), bool)
    mascara[:, :50] = True
    red([[20, 50, 6, 6, 0.9], [80, 50, 6, 6, 0.9]])
    r = da.detectar_lesiones(img, mascara)
    assert len(r) == 1 and r[0]["x1"] < 50


def test_sin_modelo_no_detecta(monkeypatch):
    monkeypatch.setattr(da, "_red", None)
    monkeypatch.setattr(da, "_red_cargada", True)
    assert da.disponible() is False and da.detectar_lesiones(ROSTRO) == []


# ------------------------------------------------------------------ RF-13: SSIM
def test_ssim_valores_de_referencia():
    assert ssim(ROSTRO, ROSTRO) == pytest.approx(1.0, abs=1e-6)
    ruido = np.clip(ROSTRO.astype(int) + np.random.default_rng(0).integers(-40, 40, ROSTRO.shape), 0, 255).astype(np.uint8)
    assert 0 < ssim(ROSTRO, ruido) < 0.9


# ------------------------------------------------------------------ integración en el procesamiento
def _jpg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def _girada(img, a, e):
    h, w = img.shape[:2]
    return cv2.warpAffine(img, cv2.getRotationMatrix2D((w / 2, h / 2), a, e), (w, h), borderMode=cv2.BORDER_REPLICATE)


def test_seguimiento_real_mejora_ssim_y_compara_lesiones(client, doc, monkeypatch):
    # detector de prueba: en la referencia 2 lesiones; en la nueva una persiste y aparece otra
    llamadas = []

    def detector(img, mascara=None):
        llamadas.append(1)
        return [caja(400, 700), caja(650, 750)] if len(llamadas) == 1 else [caja(402, 702), caja(500, 900)]

    monkeypatch.setattr(da, "disponible", lambda: True)
    monkeypatch.setattr(da, "detectar_lesiones", detector)
    p = crear_paciente(client, doc)
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, headers=doc, files={
        "imagen_referencia": ("r.jpg", _jpg(ROSTRO), "image/jpeg"),
        "imagen_nueva": ("n.jpg", _jpg(_girada(ROSTRO, 6, 1.1)), "image/jpeg")})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["ssim_despues"] > s["ssim_antes"]  # la alineación mejora la similitud (RF-13)
    assert (s["lesiones_referencia"], s["lesiones_nueva"], s["lesiones_nuevas"], s["lesiones_persistentes"], s["lesiones_resueltas"]) == (2, 2, 1, 1, 1)
    assert client.get(s["url_imagen_lesiones"], headers=doc).status_code == 200


def test_sin_modelo_el_seguimiento_funciona_igual(client, doc, monkeypatch):
    monkeypatch.setattr(da, "disponible", lambda: False)
    p = crear_paciente(client, doc)
    r = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, headers=doc, files={
        "imagen_referencia": ("r.jpg", _jpg(ROSTRO), "image/jpeg"), "imagen_nueva": ("n.jpg", _jpg(_girada(ROSTRO, 3, 1.05)), "image/jpeg")})
    assert r.status_code == 201 and r.json()["lesiones_nueva"] is None and r.json()["ssim_despues"] is not None
