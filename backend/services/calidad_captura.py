"""Control de calidad de la foto de seguimiento (RF-03).

Usa los puntos faciales de MediaPipe para decirle al dermatólogo, apenas saca la foto, si sirve
para comparar con la consulta anterior y qué corregir. Cada control devuelve un nivel:
  - "error": la foto no debería usarse (el análisis sería poco confiable)
  - "aviso": se puede usar, pero conviene repetirla
  - "ok"
"""
import math
from typing import Optional

import cv2
import numpy as np

from core.config import settings
from services.analisis_colorimetrico import _calcular_mascara_rostro, _convertir_a_lab_real
from services.procesamiento_imagenes import detectar_landmarks

# Índices de MediaPipe Face Mesh
BORDE_IZQ, BORDE_DER = 234, 454      # contorno del rostro a la altura de los pómulos
OJO_EXT_IZQ, OJO_EXT_DER = 33, 263   # comisuras externas de los ojos
NARIZ = 1


def _medidas(imagen_bgr: np.ndarray, puntos) -> dict:
    alto, ancho = imagen_bgr.shape[:2]
    izq, der, nariz = puntos[BORDE_IZQ], puntos[BORDE_DER], puntos[NARIZ]
    ancho_rostro = math.dist(izq, der)
    oi, od = puntos[OJO_EXT_IZQ], puntos[OJO_EXT_DER]
    inclinacion = math.degrees(math.atan2(od[1] - oi[1], od[0] - oi[0]))
    # Giro lateral: dónde cae la nariz entre ambos bordes del rostro (0,5 = de frente)
    posicion_nariz = (nariz[0] - izq[0]) / (der[0] - izq[0]) if der[0] != izq[0] else 0.5

    mascara = _calcular_mascara_rostro(puntos, alto, ancho) == 255
    lab = _convertir_a_lab_real(imagen_bgr)
    luz = float(lab[..., 0][mascara].mean())
    gris = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)
    quemados = float((gris[mascara] >= 250).mean())

    x, y, w, h = cv2.boundingRect(np.array(puntos, np.int32))
    recorte = gris[max(0, y):y + h, max(0, x):x + w]
    recorte = cv2.resize(recorte, (256, int(256 * recorte.shape[0] / max(1, recorte.shape[1]))))
    nitidez = float(cv2.Laplacian(recorte, cv2.CV_64F).var())

    return {
        "ancho_rostro": ancho_rostro / ancho,
        "descentrado": math.hypot(nariz[0] / ancho - 0.5, nariz[1] / alto - 0.5),
        "inclinacion": inclinacion,
        "giro": posicion_nariz - 0.5,
        "luz": luz,
        "sobreexpuesto": quemados,
        "nitidez": nitidez,
    }


def _control(codigo: str, nivel: str, mensaje: str, valor: float) -> dict:
    return {"codigo": codigo, "nivel": nivel, "mensaje": mensaje, "valor": round(valor, 3)}


def evaluar_captura(imagen_bgr: np.ndarray, referencia_bgr: Optional[np.ndarray] = None) -> dict:
    s = settings
    puntos = detectar_landmarks(imagen_bgr)
    if puntos is None:
        return {
            "apta": False,
            "controles": [_control("rostro", "error", "No se detecta un rostro. Encuadrá la cara completa dentro del óvalo, "
                                   "de frente y sin taparla (pelo, manos, barbijo).", 0)],
            "medidas": None,
        }
    m = _medidas(imagen_bgr, puntos)
    c = [_control("rostro", "ok", f"Rostro detectado ({len(puntos)} puntos faciales).", len(puntos))]

    if m["ancho_rostro"] < s.CAPTURA_ANCHO_ROSTRO_MIN:
        c.append(_control("distancia", "error", "El rostro se ve muy chico: acercá el celular.", m["ancho_rostro"]))
    elif m["ancho_rostro"] > s.CAPTURA_ANCHO_ROSTRO_MAX:
        c.append(_control("distancia", "error", "El rostro está demasiado cerca y se corta: alejá un poco el celular.", m["ancho_rostro"]))
    else:
        c.append(_control("distancia", "ok", "Distancia adecuada.", m["ancho_rostro"]))

    if m["descentrado"] > s.CAPTURA_DESCENTRADO_MAX:
        c.append(_control("centrado", "aviso", "El rostro no está centrado: ubicalo en el medio del óvalo.", m["descentrado"]))
    else:
        c.append(_control("centrado", "ok", "Rostro centrado.", m["descentrado"]))

    if abs(m["inclinacion"]) > s.CAPTURA_INCLINACION_MAX_GRADOS:
        lado = "derecha" if m["inclinacion"] > 0 else "izquierda"
        c.append(_control("inclinacion", "error", f"La cabeza está inclinada hacia la {lado} ({abs(m['inclinacion']):.0f}°): "
                          "pedile al paciente que la enderece.", m["inclinacion"]))
    else:
        c.append(_control("inclinacion", "ok", "Cabeza derecha.", m["inclinacion"]))

    if abs(m["giro"]) > s.CAPTURA_GIRO_MAX:
        c.append(_control("giro", "error", "El paciente está girado hacia un costado: pedile que mire de frente a la cámara.", m["giro"]))
    else:
        c.append(_control("giro", "ok", "Rostro de frente.", m["giro"]))

    if m["luz"] < s.CAPTURA_LUZ_MIN:
        c.append(_control("luz", "error", "Falta luz: encendé la luz del consultorio o acercá al paciente a la ventana.", m["luz"]))
    elif m["luz"] > s.CAPTURA_LUZ_MAX or m["sobreexpuesto"] > s.CAPTURA_SOBREEXPUESTO_MAX:
        c.append(_control("luz", "error", "Hay demasiada luz o reflejos (zonas quemadas): evitá el flash y la luz directa.", m["luz"]))
    else:
        c.append(_control("luz", "ok", "Iluminación adecuada.", m["luz"]))

    if m["nitidez"] < s.CAPTURA_NITIDEZ_MIN:
        c.append(_control("nitidez", "aviso", "La foto está algo borrosa: sostené el celular firme y tocá la pantalla para enfocar.", m["nitidez"]))
    else:
        c.append(_control("nitidez", "ok", "Foto nítida.", m["nitidez"]))

    comparacion = None
    if referencia_bgr is not None:
        pr = detectar_landmarks(referencia_bgr)
        if pr is not None:
            r = _medidas(referencia_bgr, pr)
            dif_escala = abs(m["ancho_rostro"] - r["ancho_rostro"]) / r["ancho_rostro"]
            dif_luz = m["luz"] - r["luz"]
            comparacion = {"dif_escala": round(dif_escala, 3), "dif_luz": round(dif_luz, 2)}
            if dif_escala > s.CAPTURA_DIF_ESCALA_MAX:
                que = "más cerca" if m["ancho_rostro"] > r["ancho_rostro"] else "más lejos"
                c.append(_control("igual_distancia", "aviso", f"Estás {que} que en la consulta anterior: ajustá la distancia "
                                  "hasta que el rostro coincida con la silueta de referencia.", dif_escala))
            else:
                c.append(_control("igual_distancia", "ok", "Misma distancia que la consulta anterior.", dif_escala))
            if abs(dif_luz) > s.CAPTURA_DIF_LUZ_MAX:
                que = "más clara" if dif_luz > 0 else "más oscura"
                c.append(_control("igual_luz", "aviso", f"La iluminación es {que} que en la consulta anterior: el cambio de luz "
                                  "puede confundirse con un cambio de color de la piel. Usá la misma luz y el mismo lugar.", dif_luz))
            else:
                c.append(_control("igual_luz", "ok", "Iluminación similar a la consulta anterior.", dif_luz))

    return {
        "apta": not any(x["nivel"] == "error" for x in c),
        "controles": c,
        "medidas": {k: round(v, 3) for k, v in m.items()},
        "comparacion": comparacion,
    }
