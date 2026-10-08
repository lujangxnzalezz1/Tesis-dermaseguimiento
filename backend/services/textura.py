"""Textura de la piel: líneas/arrugas, poros y brillo de la zona T.

Igual que el análisis de manchas, son índices para COMPARAR consultas del mismo paciente, no un
diagnóstico. Cada medida se calcula en zonas del rostro ubicadas con los puntos de MediaPipe; la foto
nueva se analiza ya alineada y con las zonas de la referencia, así que se mide la misma superficie.

Escala física: la distancia entre las pupilas (puntos 468 y 473) se toma como 63 mm, el promedio en
adultos. Con ella las medidas se expresan en mm y cm² (estimados), sin depender del zoom de la foto.

  - Líneas/arrugas: filtro de Frangi (realce de estructuras alargadas oscuras, usado en la literatura de
    detección de arrugas) sobre la luminosidad L* normalizada por su entorno, en frente, entrecejo y
    contorno externo de los ojos. Índice: mm de línea por cm² de piel.
  - Poros: puntos pequeños, redondos y más oscuros que su entorno en las mejillas. Índice: poros por
    cm². Solo se mide si la foto tiene detalle suficiente (≥ CAPTURA_PX_POR_MM_POROS); si no, None.
  - Brillo: zonas de la zona T mucho más claras y menos saturadas que la piel de alrededor (reflejo de
    la luz en la grasa). Índice: % de la zona T. Depende de la luz: compararlo solo con fotos tomadas
    en el mismo lugar.
"""
from typing import Optional

import cv2
import numpy as np
from skimage.filters import frangi
from skimage.morphology import skeletonize

from core.config import settings
from services.analisis_colorimetrico import _convertir_a_lab_real

DISTANCIA_PUPILAS_MM = 63.0
PUPILAS = (468, 473)

# Contornos con la topología de MediaPipe Face Mesh («derecho»/«izquierdo» = del paciente)
FRENTE = [103, 67, 109, 10, 338, 297, 332, 334, 296, 336, 9, 107, 66, 105, 63]
ENTRECEJO = [107, 9, 336, 285, 8, 55]
NARIZ_T = [168, 6, 197, 195, 5, 4, 1, 45, 275, 122, 351, 196, 419]
MEJILLAS = {
    "derecha": [117, 118, 101, 36, 205, 187, 147, 123, 116],
    "izquierda": [346, 347, 330, 266, 425, 411, 376, 352, 345],
}
CEJAS = ([70, 63, 105, 66, 107, 55, 65, 52, 53, 46], [300, 293, 334, 296, 336, 285, 295, 282, 283, 276])
OJO_EXTERNO = {"derecho": (33, 130), "izquierdo": (263, 359)}  # comisura externa y punto del borde


def _p(puntos, idx):
    return np.array([puntos[i] for i in idx], np.int32)


def escala_px_por_mm(puntos) -> Optional[float]:
    if len(puntos) <= max(PUPILAS):
        return None
    d = float(np.linalg.norm(np.array(puntos[PUPILAS[0]], float) - np.array(puntos[PUPILAS[1]], float)))
    return d / DISTANCIA_PUPILAS_MM if d > 0 else None


def _poligono(puntos, idx, alto, ancho) -> np.ndarray:
    m = np.zeros((alto, ancho), np.uint8)
    cv2.fillConvexPoly(m, cv2.convexHull(_p(puntos, idx)), 255)
    return m == 255


def _ovalo_interior(puntos, alto, ancho, escala) -> np.ndarray:
    """Rostro sin su borde (≈ 6 mm): ahí el pelo y la sombra del contorno parecen líneas."""
    m = np.zeros((alto, ancho), np.uint8)
    cv2.fillConvexPoly(m, cv2.convexHull(np.array(puntos, np.int32)), 255)
    return cv2.distanceTransform(m, cv2.DIST_L2, 3) > 6 * escala


def _patas_de_gallo(puntos, lado, alto, ancho, escala, interior) -> np.ndarray:
    """Rectángulo hacia afuera de la comisura externa del ojo (≈ 14 × 16 mm), sin el borde del rostro."""
    comisura, _ = OJO_EXTERNO[lado]
    cx, cy = puntos[comisura]
    hacia_afuera = 1 if cx > puntos[1][0] else -1
    x0 = cx + hacia_afuera * 3 * escala
    x1 = x0 + hacia_afuera * 14 * escala
    m = np.zeros((alto, ancho), np.uint8)
    cv2.rectangle(m, (int(min(x0, x1)), int(cy - 8 * escala)), (int(max(x0, x1)), int(cy + 8 * escala)), 255, -1)
    return (m == 255) & interior


def zonas(puntos, alto: int, ancho: int) -> dict:
    escala = escala_px_por_mm(puntos) or 1.0
    interior = _ovalo_interior(puntos, alto, ancho, escala)
    # Las cejas son líneas oscuras de verdad: se excluyen con un margen de ≈ 3 mm
    cejas = np.zeros((alto, ancho), np.uint8)
    for idx in CEJAS:
        cv2.fillConvexPoly(cejas, cv2.convexHull(_p(puntos, idx)), 255)
    interior_cejas = interior & (cv2.distanceTransform(255 - cejas, cv2.DIST_L2, 3) > 3 * escala)
    return {
        "frente": _poligono(puntos, FRENTE, alto, ancho) & interior_cejas,
        "entrecejo": _poligono(puntos, ENTRECEJO, alto, ancho) & interior_cejas,
        "patas_de_gallo": _patas_de_gallo(puntos, "derecho", alto, ancho, escala, interior) | _patas_de_gallo(puntos, "izquierdo", alto, ancho, escala, interior),
        "mejillas": _poligono(puntos, MEJILLAS["derecha"], alto, ancho) | _poligono(puntos, MEJILLAS["izquierda"], alto, ancho),
        "zona_t": _poligono(puntos, FRENTE, alto, ancho) | _poligono(puntos, NARIZ_T, alto, ancho),
    }


def _l_normalizada(L: np.ndarray, escala: float) -> np.ndarray:
    """L* dividida por su promedio local (≈ 6 mm): quita las sombras suaves y la diferencia de exposición.
    El promedio es suave, así que se calcula sobre una copia chica (mucho más rápido) y se amplía."""
    f = min(1.0, 2.0 / escala)
    chica = cv2.resize(L, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else L
    fondo = cv2.GaussianBlur(chica, (0, 0), max(2.0, 6 * escala * f))
    if f < 1:
        fondo = cv2.resize(fondo, (L.shape[1], L.shape[0]), interpolation=cv2.INTER_LINEAR)
    return L / np.maximum(fondo, 1.0)


def _cm2(pixeles: int, escala: float) -> float:
    return pixeles / (escala * 10) ** 2


def lineas(Ln: np.ndarray, zona: np.ndarray, escala: float) -> tuple[Optional[float], np.ndarray]:
    """mm de línea por cm² de piel dentro de `zona`, y la máscara de las líneas detectadas."""
    vacia = np.zeros(zona.shape, bool)
    if zona.sum() < 200:
        return None, vacia
    ys, xs = np.where(zona)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    recorte = Ln[y0:y1, x0:x1].astype(np.float64)
    sigmas = np.linspace(max(0.8, 0.3 * escala), max(1.5, 1.0 * escala), 4)
    resp = frangi(recorte, sigmas=sigmas, black_ridges=True)
    resp[~zona[y0:y1, x0:x1]] = 0
    lin = (resp > settings.TEXTURA_UMBRAL_FRANGI) & (recorte < 0.985)  # realce alto y realmente más oscura que su entorno
    n, et, st, _ = cv2.connectedComponentsWithStats(lin.astype(np.uint8), connectivity=8)
    largo_min = settings.TEXTURA_LARGO_MIN_LINEA_MM * escala
    final = np.zeros_like(lin)
    for i in range(1, n):
        w, h = st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        if max(w, h) >= largo_min:
            final |= et == i
    esqueleto = skeletonize(final)
    largo_mm = esqueleto.sum() / escala
    mascara = vacia.copy()
    mascara[y0:y1, x0:x1] = final
    return round(float(largo_mm / _cm2(int(zona.sum()), escala)), 2), mascara


def poros(Ln: np.ndarray, zona: np.ndarray, escala: float) -> tuple[Optional[float], list]:
    """Poros por cm² en `zona` (None si la foto no tiene detalle suficiente) y sus centros."""
    if escala < settings.TEXTURA_PX_POR_MM_POROS or zona.sum() < 200:
        return None, []
    k = max(3, int(round(0.8 * escala)) | 1)
    cerrada = cv2.morphologyEx(Ln.astype(np.float32), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    hueco = (cerrada - Ln) > settings.TEXTURA_UMBRAL_POROS  # más oscuro que lo que lo rodea, a escala de un poro
    hueco &= zona
    n, et, st, cen = cv2.connectedComponentsWithStats(hueco.astype(np.uint8), connectivity=8)
    a_min, a_max = np.pi * (0.04 * escala) ** 2, np.pi * (0.35 * escala) ** 2
    centros = []
    for i in range(1, n):
        a, w, h = st[i, cv2.CC_STAT_AREA], st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        if a_min <= a <= a_max and max(w, h) <= 2.2 * max(1, min(w, h)):
            centros.append((float(cen[i][0]), float(cen[i][1])))
    return round(len(centros) / _cm2(int(zona.sum()), escala), 1), centros


def brillo(lab: np.ndarray, zona: np.ndarray) -> tuple[Optional[float], np.ndarray]:
    """% de la zona T con reflejo: bastante más clara y menos saturada que la mediana de esa zona."""
    vacia = np.zeros(zona.shape, bool)
    if zona.sum() < 200:
        return None, vacia
    L, croma = lab[..., 0], np.hypot(lab[..., 1], lab[..., 2])
    l_med, c_med = float(np.median(L[zona])), float(np.median(croma[zona]))
    reflejo = zona & (L > l_med * (1 + settings.TEXTURA_BRILLO_L_RELATIVO)) & (croma < c_med * 0.8)
    reflejo = cv2.morphologyEx(reflejo.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) == 1
    return round(float(100 * reflejo.sum() / zona.sum()), 2), reflejo


def analizar(imagen_bgr: np.ndarray, puntos) -> Optional[dict]:
    """`puntos` en la geometría de `imagen_bgr` (para la foto alineada, los de la referencia)."""
    escala = escala_px_por_mm(puntos)
    if not escala:
        return None
    alto, ancho = imagen_bgr.shape[:2]
    z = zonas(puntos, alto, ancho)
    lab = _convertir_a_lab_real(imagen_bgr)
    Ln = _l_normalizada(lab[..., 0], escala)
    # Las líneas no necesitan más de ≈ 8 px/mm: en fotos grandes se analizan en una copia reducida (más rápido)
    f = min(1.0, 8.0 / escala)
    chico = (lambda m: cv2.resize(m.astype(np.uint8), None, fx=f, fy=f, interpolation=cv2.INTER_NEAREST) == 1) if f < 1 else (lambda m: m)
    Ln_l = cv2.resize(Ln, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else Ln
    por_zona, mascara_chica = {}, np.zeros(Ln_l.shape, bool)
    for nombre in ("frente", "entrecejo", "patas_de_gallo"):
        v, m = lineas(Ln_l, chico(z[nombre]), escala * f)
        por_zona[nombre] = v
        mascara_chica |= m
    mascara_lineas = cv2.resize(mascara_chica.astype(np.uint8), (ancho, alto), interpolation=cv2.INTER_NEAREST) == 1 if f < 1 else mascara_chica
    validos = [v for v in por_zona.values() if v is not None]
    densidad_poros, centros = poros(Ln, z["mejillas"], escala)
    pct_brillo, mascara_brillo = brillo(lab, z["zona_t"])
    return {
        "px_por_mm": round(escala, 2),
        "lineas_mm_cm2": round(float(np.mean(validos)), 2) if validos else None,
        "lineas_por_zona": por_zona,
        "poros_cm2": densidad_poros,
        "brillo_pct": pct_brillo,
        "_mascara_lineas": mascara_lineas,
        "_centros_poros": centros,
        "_mascara_brillo": mascara_brillo,
    }


def resumen(r: Optional[dict]) -> Optional[dict]:
    return {k: v for k, v in r.items() if not k.startswith("_")} if r else None


def dibujar(imagen_bgr: np.ndarray, puntos, r: dict) -> np.ndarray:
    """Foto (alineada) con las zonas analizadas, las líneas (naranja), los poros (puntos celestes) y el brillo (blanco)."""
    out = imagen_bgr.copy()
    alto, ancho = out.shape[:2]
    g = max(1, ancho // 600)
    for m in zonas(puntos, alto, ancho).values():
        cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, cs, -1, (170, 170, 170), g)
    out[r["_mascara_lineas"]] = (0, 140, 255)
    brillo_m = r["_mascara_brillo"]
    out[brillo_m] = (0.4 * out[brillo_m] + 0.6 * np.array([255, 255, 255])).astype(np.uint8)
    for x, y in r["_centros_poros"]:
        cv2.circle(out, (int(x), int(y)), max(2, g + 1), (230, 200, 40), -1)
    return out
