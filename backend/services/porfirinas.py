"""Porfirinas en una foto tomada con luz ultravioleta (lámpara de Wood o linterna UV de ≈ 365-405 nm).

Bajo luz UV, las porfirinas que produce Cutibacterium acnes en los poros emiten una fluorescencia
rojo-anaranjada: se ven como puntitos naranjas sobre un fondo violeta/azul. Es la técnica que usan los
equipos de análisis facial; aquí se cuentan esos puntos.

Se cuentan zonas pequeñas cuyo tono es rojo-anaranjado, bien saturadas y más brillantes que lo que las
rodea. Si se encuentra el rostro, se cuenta solo dentro de él y se expresa por cm² (escala con la
distancia entre pupilas); si no (fotos UV muy oscuras), se cuenta en toda la foto y se informa la
cantidad. Es un índice para comparar consultas; no diagnostica.
"""
from typing import Optional

import cv2
import numpy as np

from core.config import settings
from services.textura import escala_px_por_mm


def analizar(imagen_bgr: np.ndarray, puntos=None) -> dict:
    alto, ancho = imagen_bgr.shape[:2]
    hsv = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    tono = (h <= settings.UV_TONO_MAX) | (h >= 170)  # rojo-anaranjado (OpenCV: tono 0-180)
    k = max(9, (min(alto, ancho) // 60) | 1)
    resalte = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    candidato = tono & (s >= settings.UV_SATURACION_MIN) & (resalte >= settings.UV_RESALTE_MIN)

    rostro: Optional[np.ndarray] = None
    escala = escala_px_por_mm(puntos) if puntos else None
    if puntos:
        m = np.zeros((alto, ancho), np.uint8)
        cv2.fillConvexPoly(m, cv2.convexHull(np.array(puntos, np.int32)), 255)
        rostro = m == 255
        candidato &= rostro

    n, et, st, cen = cv2.connectedComponentsWithStats(candidato.astype(np.uint8), connectivity=8)
    area_max = max(30, int(alto * ancho * 0.0015))
    centros = [(float(cen[i][0]), float(cen[i][1])) for i in range(1, n) if 3 <= st[i, cv2.CC_STAT_AREA] <= area_max]

    por_cm2 = None
    if rostro is not None and escala:
        cm2 = rostro.sum() / (escala * 10) ** 2
        por_cm2 = round(float(len(centros) / cm2), 2) if cm2 > 0 else None
    return {"cantidad": len(centros), "por_cm2": por_cm2, "rostro_detectado": rostro is not None, "_centros": centros}


def resumen(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def dibujar(imagen_bgr: np.ndarray, r: dict) -> np.ndarray:
    out = imagen_bgr.copy()
    rad = max(4, out.shape[1] // 150)
    for x, y in r["_centros"]:
        cv2.circle(out, (int(x), int(y)), rad, (80, 255, 255), max(1, rad // 3))
    return out
