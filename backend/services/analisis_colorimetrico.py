import cv2
import numpy as np

# Delta E (CIE76) por encima de este valor se considera un cambio de color
# muy marcado; se usa solo para escalar el mapa de calor a un rango legible.
DELTA_E_MAXIMO_VISUAL = 30.0


def _convertir_a_lab_real(imagen_bgr: np.ndarray) -> np.ndarray:
    """Convierte una imagen BGR al espacio CIE L*a*b* con sus rangos reales
    (L: 0-100, a/b: aprox. -128 a 127), en vez de la escala 0-255 interna
    que usa OpenCV."""
    lab_opencv = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab_opencv[..., 0] * (100.0 / 255.0)
    a = lab_opencv[..., 1] - 128.0
    b = lab_opencv[..., 2] - 128.0
    return np.stack([L, a, b], axis=-1)


def _calcular_mascara_rostro(puntos, alto: int, ancho: int) -> np.ndarray:
    """Genera una máscara binaria con la región del rostro (envolvente
    convexa de los landmarks), para no comparar colores del fondo."""
    mascara = np.zeros((alto, ancho), dtype=np.uint8)
    envolvente = cv2.convexHull(np.array(puntos, dtype=np.int32))
    cv2.fillConvexPoly(mascara, envolvente, 255)
    return mascara


def _generar_mapa_calor(delta_e_mapa: np.ndarray, mascara: np.ndarray) -> np.ndarray:
    """Genera una imagen coloreada (mapa de calor) donde el color indica
    cuánto cambió el tono de piel en cada punto entre las dos capturas."""
    recortado = np.clip(delta_e_mapa, 0, DELTA_E_MAXIMO_VISUAL)
    normalizado = (recortado / DELTA_E_MAXIMO_VISUAL * 255).astype(np.uint8)
    mapa_color = cv2.applyColorMap(normalizado, cv2.COLORMAP_JET)
    mapa_color[mascara == 0] = (40, 40, 40)
    return mapa_color


def analizar_color(imagen_referencia_bgr: np.ndarray, imagen_alineada_bgr: np.ndarray, puntos_referencia):
    """Compara el color de piel entre la imagen de referencia y la nueva
    captura (ya alineada geométricamente), en espacio CIE L*a*b*.

    Devuelve el Delta E (CIE76) promedio dentro del rostro, los valores
    L*a*b* promedio de cada imagen, y un mapa de calor visual de las
    diferencias."""
    alto, ancho = imagen_referencia_bgr.shape[:2]
    mascara = _calcular_mascara_rostro(puntos_referencia, alto, ancho)
    indices_rostro = mascara == 255

    if not np.any(indices_rostro):
        return {
            "exito": False,
            "error": "No se pudo delimitar la región del rostro para el análisis de color.",
        }

    lab_referencia = _convertir_a_lab_real(imagen_referencia_bgr)
    lab_alineada = _convertir_a_lab_real(imagen_alineada_bgr)

    delta_e_mapa = np.sqrt(np.sum((lab_alineada - lab_referencia) ** 2, axis=-1))
    delta_e_promedio = float(np.mean(delta_e_mapa[indices_rostro]))

    l_referencia, a_referencia, b_referencia = (
        float(np.mean(lab_referencia[..., canal][indices_rostro])) for canal in range(3)
    )
    l_nueva, a_nueva, b_nueva = (
        float(np.mean(lab_alineada[..., canal][indices_rostro])) for canal in range(3)
    )

    mapa_calor = _generar_mapa_calor(delta_e_mapa, mascara)

    return {
        "exito": True,
        "delta_e_promedio": delta_e_promedio,
        "l_referencia": l_referencia,
        "a_referencia": a_referencia,
        "b_referencia": b_referencia,
        "l_nueva": l_nueva,
        "a_nueva": a_nueva,
        "b_nueva": b_nueva,
        "mapa_calor": mapa_calor,
    }
