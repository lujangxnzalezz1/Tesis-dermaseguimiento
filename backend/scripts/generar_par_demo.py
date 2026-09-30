"""Genera un par de fotos de seguimiento DE DEMOSTRACIÓN a partir de una foto frontal (rostro sintético).

La «segunda consulta» se obtiene de la misma foto aplicando lo que cambia entre sesiones reales:
rotación, escala y desplazamiento (ángulo y distancia de la cámara), cambio de iluminación y un
enrojecimiento controlado en las mejillas (el cambio clínico simulado que el sistema debe detectar).

    python -m scripts.generar_par_demo foto_base.jpg carpeta_salida/

IMPORTANTE: son imágenes sintéticas para probar el sistema, no casos clínicos reales.
"""
import os
import sys

import cv2
import numpy as np

from services.procesamiento_imagenes import detectar_landmarks

# Contorno aproximado de cada mejilla en la topología de MediaPipe Face Mesh
MEJILLA_IZQ = [116, 117, 118, 101, 36, 205, 187, 123]
MEJILLA_DER = [345, 346, 347, 330, 266, 425, 411, 352]


def enrojecer_mejillas(img, puntos, intensidad=0.22):
    """Eritema leve: sube el rojo y baja verde/azul de la propia piel (no pinta un color encima)."""
    mascara = np.zeros(img.shape[:2], np.float32)
    for indices in (MEJILLA_IZQ, MEJILLA_DER):
        cv2.fillConvexPoly(mascara, cv2.convexHull(np.array([puntos[i] for i in indices], np.int32)), 1.0)
    lado = max(5, int(img.shape[1] * 0.06) | 1)
    mascara = cv2.GaussianBlur(mascara, (lado * 2 + 1, lado * 2 + 1), 0)[..., None] * intensidad
    piel = img.astype(np.float32)
    enrojecida = piel * np.array([0.80, 0.82, 1.10], np.float32)  # BGR
    return np.clip(piel * (1 - mascara) + enrojecida * mascara, 0, 255).astype(np.uint8)


def cambiar_toma(img, angulo=4.0, escala=1.10, dx=0.02, dy=-0.015, brillo=1.10, calidez=6):
    # Escala > 1 (cámara algo más cerca) para que el giro no deje bordes vacíos en la foto
    alto, ancho = img.shape[:2]
    m = cv2.getRotationMatrix2D((ancho / 2, alto / 2), angulo, escala)
    m[0, 2] += dx * ancho
    m[1, 2] += dy * alto
    girada = cv2.warpAffine(img, m, (ancho, alto), borderMode=cv2.BORDER_REPLICATE)
    luz = girada.astype(np.float32) * brillo
    luz[..., 2] += calidez  # luz algo más cálida en el consultorio
    luz[..., 0] -= calidez
    return np.clip(luz, 0, 255).astype(np.uint8)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    base = cv2.imread(sys.argv[1])
    if base is None:
        raise SystemExit("No se pudo leer la foto base.")
    puntos = detectar_landmarks(base)
    if puntos is None:
        raise SystemExit("MediaPipe no detectó un rostro en la foto base. Probá con otra foto frontal.")
    os.makedirs(sys.argv[2], exist_ok=True)
    ref = os.path.join(sys.argv[2], "consulta1_referencia.jpg")
    nueva = os.path.join(sys.argv[2], "consulta2_seguimiento.jpg")
    cv2.imwrite(ref, base, [cv2.IMWRITE_JPEG_QUALITY, 92])
    cv2.imwrite(nueva, cambiar_toma(enrojecer_mejillas(base, puntos)), [cv2.IMWRITE_JPEG_QUALITY, 92])
    segunda = detectar_landmarks(cv2.imread(nueva))
    print(f"Rostro detectado: {len(puntos)} puntos (consulta 1), {len(segunda) if segunda else 0} puntos (consulta 2)")
    print(f"Guardadas:\n  {ref}\n  {nueva}")


if __name__ == "__main__":
    main()
