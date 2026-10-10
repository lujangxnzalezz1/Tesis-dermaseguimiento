"""Análisis de manchas (zonas hiperpigmentadas) del rostro.

Es una ampliación del análisis colorimétrico: no diagnostica ni clasifica el tipo de mancha. Mide, en
cada foto, qué parte de la piel es claramente más oscura que la piel que la rodea, para poder comparar
esa medida entre consultas del mismo paciente.

Por qué es comparable entre consultas:
  - Cada píxel se compara con la luminosidad L* de la piel de su alrededor en la MISMA foto (fondo
    local), no con un valor fijo: un cambio general de luz afecta a la mancha y a su entorno por igual.
  - La foto nueva se analiza ya alineada, con la máscara de piel de la referencia: se mide exactamente
    la misma superficie del rostro en ambas consultas.
  - El umbral es relativo (la zona debe ser un X % más oscura que su entorno), así que no depende de
    la exposición de la cámara.
  - Se excluyen ojos y cejas, ojeras (las mide el RF-16), labios, nariz y el borde del rostro (pelo,
    sombra del contorno), y se descartan las zonas alargadas (surcos y pliegues como el nasogeniano,
    líneas de expresión), porque son sombras del relieve y no pigmento.

Métricas:
  - area_pct: porcentaje de la piel analizada ocupado por manchas (indicador principal)
  - cantidad: cantidad de manchas (zonas separadas)
  - contraste_medio: cuánto más oscuras son, en promedio, que la piel de alrededor (en % de L*)

Limitaciones: una sombra marcada por iluminación lateral, el vello facial o el maquillaje pueden
detectarse como manchas; por eso la captura guiada pide luz frontal y pareja (RF-03).
"""
from typing import Optional

import cv2
import numpy as np

from core.config import settings
from services.analisis_colorimetrico import _convertir_a_lab_real
from services.periorbital import REGIONES

# Topología de MediaPipe Face Mesh
OVALO = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176,
         149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
# Zonas excluidas y su margen (fracción del ancho del rostro): las comisuras de los labios y de los ojos
# quedan en sombra por el relieve, por eso llevan un margen mayor.
EXCLUIDAS = {
    "ojo_ceja_derecho": ([33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246,
                          70, 63, 105, 66, 107, 55, 65, 52, 53, 46], 0.04),
    "ojo_ceja_izquierdo": ([263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466,
                            300, 293, 334, 296, 336, 285, 295, 282, 283, 276], 0.04),
    "labios": ([61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185], 0.06),
    # Nariz completa: sus costados y alas quedan en sombra por el relieve, no por pigmento
    "nariz": ([168, 6, 197, 195, 5, 4, 1, 19, 94, 2, 129, 358, 98, 327, 49, 279, 48, 278, 64, 294, 209, 429, 193, 417], 0.02),
}


ANCHO_TRABAJO = 1400  # las manchas no necesitan más detalle: en fotos grandes se trabaja sobre una copia reducida


def _factor(ancho: int) -> float:
    return min(1.0, ANCHO_TRABAJO / ancho)


def mascara_piel(puntos, alto: int, ancho: int) -> np.ndarray:
    """Piel analizable (en la resolución original): se calcula en tamaño de trabajo y se amplía."""
    f = _factor(ancho)
    if f < 1:
        chica = _mascara_piel([(x * f, y * f) for x, y in puntos], int(round(alto * f)), int(round(ancho * f)))
        return cv2.resize(chica.astype(np.uint8), (ancho, alto), interpolation=cv2.INTER_NEAREST) == 1
    return _mascara_piel(puntos, alto, ancho)


def _mascara_piel(puntos, alto: int, ancho: int) -> np.ndarray:
    """Piel analizable: óvalo del rostro, sin su borde, sin ojos/cejas, ojeras, labios ni fosas nasales."""
    p = lambda idx: np.array([puntos[i] for i in idx], np.int32)  # noqa: E731
    ancho_rostro = float(np.ptp(p(OVALO)[:, 0]))
    m = np.zeros((alto, ancho), np.uint8)
    cv2.fillPoly(m, [p(OVALO)], 255)
    borde = max(3, int(ancho_rostro * settings.MANCHAS_MARGEN_BORDE))
    m = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * borde + 1, 2 * borde + 1)))
    zonas = list(EXCLUIDAS.values()) + [(reg["ojera"], 0.02) for reg in REGIONES.values()]
    for idx, margen in zonas:
        z = np.zeros_like(m)
        cv2.fillConvexPoly(z, cv2.convexHull(p(idx)), 255)
        h = max(3, int(ancho_rostro * margen))
        z = cv2.dilate(z, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * h + 1, 2 * h + 1)))
        m[z == 255] = 0
    return m == 255


def _fondo_local(L: np.ndarray, piel: np.ndarray, sigma: float) -> np.ndarray:
    """Promedio de L* de la piel de alrededor de cada píxel (convolución normalizada: ignora lo que no es piel)."""
    peso = piel.astype(np.float32)
    num = cv2.GaussianBlur(L * peso, (0, 0), sigma)
    den = cv2.GaussianBlur(peso, (0, 0), sigma)
    return num / np.maximum(den, 1e-6)


def _elongacion(componente: np.ndarray) -> float:
    """Relación entre el eje largo y el corto de la zona (1 = redonda)."""
    ys, xs = np.nonzero(componente)
    if len(xs) < 5:
        return 1.0
    ev = np.linalg.eigvalsh(np.cov(np.vstack([xs, ys]).astype(np.float64)))
    return float(np.sqrt(max(ev[1], 1e-6) / max(ev[0], 1e-6)))


def detectar_manchas(imagen_bgr: np.ndarray, piel: np.ndarray) -> Optional[dict]:
    """`piel` es la máscara de `mascara_piel` calculada con los puntos de la geometría de `imagen_bgr`.
    En fotos grandes se analiza una copia reducida y la máscara de manchas se devuelve en el tamaño original."""
    alto, ancho = imagen_bgr.shape[:2]
    f = _factor(ancho)
    if f >= 1:
        return _detectar_manchas(imagen_bgr, piel)
    tam = (int(round(ancho * f)), int(round(alto * f)))
    r = _detectar_manchas(cv2.resize(imagen_bgr, tam, interpolation=cv2.INTER_AREA),
                          cv2.resize(piel.astype(np.uint8), tam, interpolation=cv2.INTER_NEAREST) == 1)
    if r is not None:
        r["mascara"] = cv2.resize(r["mascara"].astype(np.uint8), (ancho, alto), interpolation=cv2.INTER_NEAREST) == 1
    return r


def _detectar_manchas(imagen_bgr: np.ndarray, piel: np.ndarray) -> Optional[dict]:
    area_piel = int(piel.sum())
    if area_piel < 500:
        return None
    ys, xs = np.where(piel)
    ancho_rostro = float(np.ptp(xs))
    L = _convertir_a_lab_real(imagen_bgr)[..., 0]
    L = cv2.GaussianBlur(L, (0, 0), max(1.0, ancho_rostro / 400))  # quita el ruido del sensor y los poros
    fondo = _fondo_local(L, piel, ancho_rostro * settings.MANCHAS_ESCALA_FONDO)
    oscuridad = fondo - L
    relativa = oscuridad / np.maximum(fondo, 1.0)
    candidata = ((relativa >= settings.MANCHAS_UMBRAL_RELATIVO) & piel).astype(np.uint8)
    candidata = cv2.morphologyEx(candidata, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    area_min = max(4, int(area_piel * settings.MANCHAS_AREA_MIN))
    # Distancia de cada píxel al borde de la piel analizada: lo pegado al borde suele ser sombra de la zona excluida
    al_borde = cv2.distanceTransform(piel.astype(np.uint8), cv2.DIST_L2, 3) < ancho_rostro * 0.015
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(candidata, connectivity=8)
    final = np.zeros_like(candidata)
    manchas = 0
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < area_min:
            continue
        x0, y0, w0, h0 = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        recorte = (slice(y0, y0 + h0), slice(x0, x0 + w0))
        comp_r = etiquetas[recorte] == i
        if _elongacion(comp_r) > settings.MANCHAS_ELONGACION_MAX:
            continue  # surco o pliegue (sombra del relieve), no mancha
        if al_borde[recorte][comp_r].mean() > 0.5:
            continue  # sombra de un ojo, la nariz, los labios o el contorno, no mancha
        final[recorte][comp_r] = 1
        manchas += 1
    sel = final == 1
    return {
        "area_pct": round(float(100.0 * sel.sum() / area_piel), 2),
        "cantidad": manchas,
        "contraste_medio": round(float(100 * relativa[sel].mean()), 1) if manchas else 0.0,
        "mascara": sel,
    }


def dibujar_comparacion(imagen_bgr: np.ndarray, piel: np.ndarray, ref: dict, nueva: dict) -> np.ndarray:
    """Sobre la foto nueva (alineada): contorno de la piel analizada (gris), manchas de la referencia (celeste)
    y manchas actuales (naranja). Donde coinciden se ven ambos contornos."""
    out = imagen_bgr.copy()
    g = max(2, imagen_bgr.shape[1] // 450)
    for m, color in ((piel, (170, 170, 170)), (ref["mascara"], (230, 200, 40)), (nueva["mascara"], (0, 140, 255))):
        contornos, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, contornos, -1, color, g)
    return out


def resumen(r: dict) -> dict:
    """Lo que se guarda en la base (sin la máscara)."""
    return {k: v for k, v in r.items() if k != "mascara"}
