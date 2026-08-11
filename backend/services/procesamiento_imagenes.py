import os

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

# Puntos de referencia estables para calcular la transformación afín:
# ojo izquierdo (interno), ojo derecho (interno), punta de la nariz.
# Estos índices corresponden al mapa de landmarks de MediaPipe Face
# Landmarker (misma topología que el FaceMesh clásico con refine_landmarks=True).
INDICES_REFERENCIA = [133, 362, 1]

# La API clásica "mp.solutions.face_mesh" no está disponible en los wheels
# de mediapipe para macOS Apple Silicon, así que usamos la Tasks API oficial,
# que sí funciona en esta arquitectura y es la soportada a futuro.
_RUTA_MODELO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_landmarker.task")

_face_landmarker = vision.FaceLandmarker.create_from_options(
    vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_RUTA_MODELO),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=1,
        min_face_detection_confidence=0.5,
    )
)


def detectar_landmarks(imagen_bgr: np.ndarray):
    """Detecta los puntos anatómicos faciales en una imagen.
    Devuelve una lista de coordenadas (x, y) en píxeles, o None si no
    se detectó un rostro."""
    alto, ancho = imagen_bgr.shape[:2]
    imagen_rgb = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2RGB)
    imagen_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=imagen_rgb)

    resultado = _face_landmarker.detect(imagen_mp)

    if not resultado.face_landmarks:
        return None

    landmarks = resultado.face_landmarks[0]
    puntos = [(int(p.x * ancho), int(p.y * alto)) for p in landmarks]
    return puntos


def calcular_transformacion_afin(puntos_referencia, puntos_nueva):
    """Calcula la matriz de transformación afín que alinea la imagen nueva
    con la imagen de referencia, usando 3 puntos anatómicos estables."""
    origen = np.float32([puntos_nueva[i] for i in INDICES_REFERENCIA])
    destino = np.float32([puntos_referencia[i] for i in INDICES_REFERENCIA])
    matriz = cv2.getAffineTransform(origen, destino)
    return matriz


def alinear_imagen(imagen_nueva: np.ndarray, matriz, ancho: int, alto: int):
    """Aplica la transformación afín para producir una imagen alineada
    con la misma geometría que la imagen de referencia."""
    return cv2.warpAffine(imagen_nueva, matriz, (ancho, alto))


def procesar_par_de_imagenes(imagen_referencia_bgr: np.ndarray, imagen_nueva_bgr: np.ndarray):
    """Pipeline completo: detecta landmarks en ambas imágenes, calcula la
    transformación afín y devuelve la imagen nueva alineada con la de referencia.

    Devuelve un diccionario con el resultado o un mensaje de error si no
    se pudieron detectar suficientes puntos anatómicos (según RF de manejo
    de excepciones del anteproyecto)."""
    puntos_referencia = detectar_landmarks(imagen_referencia_bgr)
    puntos_nueva = detectar_landmarks(imagen_nueva_bgr)

    if puntos_referencia is None or puntos_nueva is None:
        return {
            "exito": False,
            "error": "No se detectaron suficientes puntos anatómicos de referencia. "
            "Verificá que el rostro esté bien iluminado y no esté ocluido.",
        }

    alto, ancho = imagen_referencia_bgr.shape[:2]
    matriz = calcular_transformacion_afin(puntos_referencia, puntos_nueva)
    imagen_alineada = alinear_imagen(imagen_nueva_bgr, matriz, ancho, alto)

    return {
        "exito": True,
        "imagen_alineada": imagen_alineada,
        "puntos_referencia": puntos_referencia,
        "cantidad_landmarks_referencia": len(puntos_referencia),
        "cantidad_landmarks_nueva": len(puntos_nueva),
    }
