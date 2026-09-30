"""Detección de lesiones de acné con YOLOv8 (RF-14) y comparación entre consultas (RF-15).

El modelo se entrenó con ACNE04 (Wu et al., ICCV 2019; uso académico) y se exportó a ONNX, así el
backend lo ejecuta con OpenCV DNN sin depender de la librería de entrenamiento. El modelo SOLO
localiza regiones con recuadros: no clasifica el tipo de lesión ni emite diagnóstico.
"""
import logging
import os
from typing import Optional

import cv2
import numpy as np

from core.config import settings

log = logging.getLogger("acne")
_red = None
_red_cargada = False


def _cargar_red():
    global _red, _red_cargada
    if not _red_cargada:
        _red_cargada = True
        if os.path.exists(settings.RUTA_MODELO_ACNE):
            _red = cv2.dnn.readNetFromONNX(settings.RUTA_MODELO_ACNE)
            log.info("Modelo de acné cargado: %s", settings.RUTA_MODELO_ACNE)
        else:
            log.warning("No se encontró el modelo de acné en %s: la detección queda desactivada", settings.RUTA_MODELO_ACNE)
    return _red


def disponible() -> bool:
    return _cargar_red() is not None


def detectar_lesiones(imagen_bgr: np.ndarray, mascara_rostro: Optional[np.ndarray] = None) -> list[dict]:
    """Devuelve [{x1, y1, x2, y2, confianza}] en píxeles de la imagen original."""
    red = _cargar_red()
    if red is None:
        return []
    alto, ancho = imagen_bgr.shape[:2]
    lado = settings.ACNE_IMGSZ
    # Letterbox: se escala manteniendo la proporción y se rellena con gris (igual que en el entrenamiento)
    esc = min(lado / ancho, lado / alto)
    nw, nh = round(ancho * esc), round(alto * esc)
    lienzo = np.full((lado, lado, 3), 114, np.uint8)
    dx, dy = (lado - nw) // 2, (lado - nh) // 2
    lienzo[dy:dy + nh, dx:dx + nw] = cv2.resize(imagen_bgr, (nw, nh))
    blob = cv2.dnn.blobFromImage(lienzo, 1 / 255.0, (lado, lado), swapRB=True)
    red.setInput(blob)
    salida = red.forward()[0]  # (4 + clases, N)
    salida = salida.T
    puntajes = salida[:, 4:].max(axis=1)
    keep = puntajes >= settings.ACNE_CONFIANZA_MIN
    salida, puntajes = salida[keep], puntajes[keep]
    if not len(salida):
        return []
    cx, cy, w, h = salida[:, 0], salida[:, 1], salida[:, 2], salida[:, 3]
    x1 = (cx - w / 2 - dx) / esc
    y1 = (cy - h / 2 - dy) / esc
    cajas = np.stack([x1, y1, w / esc, h / esc], axis=1)
    indices = cv2.dnn.NMSBoxes(cajas.tolist(), puntajes.tolist(), settings.ACNE_CONFIANZA_MIN, settings.ACNE_IOU_NMS)
    lesiones = []
    for i in np.array(indices).flatten():
        x, y, bw, bh = cajas[i]
        c = dict(x1=int(max(0, x)), y1=int(max(0, y)), x2=int(min(ancho, x + bw)), y2=int(min(alto, y + bh)),
                 confianza=round(float(puntajes[i]), 3))
        if mascara_rostro is not None:
            mx, my = (c["x1"] + c["x2"]) // 2, (c["y1"] + c["y2"]) // 2
            if not (0 <= my < alto and 0 <= mx < ancho and mascara_rostro[my, mx]):
                continue  # fuera del rostro (fondo, ropa)
        lesiones.append(c)
    return lesiones


def _iou(a: dict, b: dict) -> float:
    ix = max(0, min(a["x2"], b["x2"]) - max(a["x1"], b["x1"]))
    iy = max(0, min(a["y2"], b["y2"]) - max(a["y1"], b["y1"]))
    inter = ix * iy
    union = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]) + (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) - inter
    return inter / union if union > 0 else 0.0


def comparar_lesiones(referencia: list[dict], nueva: list[dict]) -> dict:
    """RF-15: con las imágenes ya alineadas, una lesión de la nueva captura es 'persistente' si se superpone
    con alguna de la referencia; si no, es 'nueva'. Las de la referencia sin pareja son 'resueltas'."""
    umbral = settings.ACNE_IOU_MISMA_LESION
    usadas = set()
    persistentes, nuevas = [], []
    for n in nueva:
        mejor, idx = 0.0, None
        for i, r in enumerate(referencia):
            if i in usadas:
                continue
            v = _iou(n, r)
            if v > mejor:
                mejor, idx = v, i
        if idx is not None and mejor >= umbral:
            usadas.add(idx)
            persistentes.append(n)
        else:
            nuevas.append(n)
    resueltas = [r for i, r in enumerate(referencia) if i not in usadas]
    return {"persistentes": persistentes, "nuevas": nuevas, "resueltas": resueltas}


def dibujar_comparacion(imagen_bgr: np.ndarray, comparacion: dict) -> np.ndarray:
    """Verde = persistente, rojo = nueva, amarillo punteado = resuelta (estaba en la referencia)."""
    out = imagen_bgr.copy()
    grosor = max(2, imagen_bgr.shape[1] // 400)
    for c in comparacion["persistentes"]:
        cv2.rectangle(out, (c["x1"], c["y1"]), (c["x2"], c["y2"]), (60, 180, 60), grosor)
    for c in comparacion["nuevas"]:
        cv2.rectangle(out, (c["x1"], c["y1"]), (c["x2"], c["y2"]), (40, 40, 230), grosor + 1)
    for c in comparacion["resueltas"]:
        x1, y1, x2, y2 = c["x1"], c["y1"], c["x2"], c["y2"]
        for x in range(x1, x2, 8):
            cv2.line(out, (x, y1), (min(x + 4, x2), y1), (0, 210, 240), grosor)
            cv2.line(out, (x, y2), (min(x + 4, x2), y2), (0, 210, 240), grosor)
        for y in range(y1, y2, 8):
            cv2.line(out, (x1, y), (x1, min(y + 4, y2)), (0, 210, 240), grosor)
            cv2.line(out, (x2, y), (x2, min(y + 4, y2)), (0, 210, 240), grosor)
    return out
