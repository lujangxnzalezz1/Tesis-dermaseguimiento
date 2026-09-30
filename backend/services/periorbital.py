"""Análisis colorimétrico de la región periorbital (ojeras) — RF-16.

La región se ubica con los puntos faciales de MediaPipe (no necesita un detector aparte). Para cada
ojo se compara el color de la zona infraorbitaria con una zona de piel malar (mejilla) de la MISMA
foto: el contraste relativo es menos sensible a cambios de iluminación entre consultas que el color
absoluto, porque la luz afecta a ambas zonas por igual.

Métricas por ojo:
  - L*, a*, b* promedio de la ojera y de la mejilla de comparación
  - contraste_L = L*(mejilla) - L*(ojera): cuánto más oscura es la ojera (mayor = más marcada)
  - delta_e = distancia CIE76 entre ojera y mejilla
"""
from typing import Optional

import cv2
import numpy as np

from services.analisis_colorimetrico import _convertir_a_lab_real

# Topología de MediaPipe Face Mesh. «derecho» e «izquierdo» son los del PACIENTE.
# Contorno: párpado inferior (de la comisura externa a la interna) y luego el borde inferior de la ojera.
REGIONES = {
    "derecho": {
        "ojera": [33, 7, 163, 144, 145, 153, 154, 155, 133, 243, 244, 233, 232, 231, 230, 229, 228, 31, 226],
        "mejilla": [117, 118, 101, 36, 205, 50],
    },
    "izquierdo": {
        "ojera": [263, 249, 390, 373, 374, 380, 381, 382, 362, 463, 464, 453, 452, 451, 450, 449, 448, 261, 446],
        "mejilla": [346, 347, 330, 266, 425, 280],
    },
}


def _mascara(puntos, indices, alto, ancho) -> np.ndarray:
    m = np.zeros((alto, ancho), np.uint8)
    cv2.fillPoly(m, [np.array([puntos[i] for i in indices], np.int32)], 255)
    return m == 255


def _lab_medio(lab, mascara):
    return [float(lab[..., c][mascara].mean()) for c in range(3)]


def analizar_periorbital(imagen_bgr: np.ndarray, puntos) -> Optional[dict]:
    """`puntos` deben corresponder a la geometría de `imagen_bgr` (para la imagen alineada se usan los
    de la referencia, porque la alineación la lleva a esa misma geometría)."""
    alto, ancho = imagen_bgr.shape[:2]
    lab = _convertir_a_lab_real(imagen_bgr)
    salida = {}
    for lado, reg in REGIONES.items():
        mo, mm = _mascara(puntos, reg["ojera"], alto, ancho), _mascara(puntos, reg["mejilla"], alto, ancho)
        if mo.sum() < 20 or mm.sum() < 20:
            return None
        o, c = _lab_medio(lab, mo), _lab_medio(lab, mm)
        salida[lado] = {
            "ojera_lab": [round(v, 2) for v in o], "mejilla_lab": [round(v, 2) for v in c],
            "contraste_L": round(c[0] - o[0], 2),
            "delta_e": round(float(np.linalg.norm(np.array(o) - np.array(c))), 2),
        }
    salida["contraste_L_promedio"] = round((salida["derecho"]["contraste_L"] + salida["izquierdo"]["contraste_L"]) / 2, 2)
    return salida


def dibujar_regiones(imagen_bgr: np.ndarray, puntos) -> np.ndarray:
    out = imagen_bgr.copy()
    g = max(2, imagen_bgr.shape[1] // 450)
    for reg in REGIONES.values():
        cv2.polylines(out, [np.array([puntos[i] for i in reg["ojera"]], np.int32)], True, (200, 60, 200), g)
        cv2.polylines(out, [np.array([puntos[i] for i in reg["mejilla"]], np.int32)], True, (230, 200, 40), g)
    return out
