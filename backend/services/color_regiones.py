"""Cambio de color por zona del rostro: qué cambió (rojez, luz, tono amarillo) y por qué pudo cambiar.

El Delta E dice CUÁNTO cambió el color; acá se separa en sus componentes CIE L*a*b*:
  - ΔL*: más clara (+) o más oscura (−)  → luz de la foto o pigmento
  - Δa*: más roja (+) o menos roja (−)   → enrojecimiento
  - Δb*: más amarilla (+) o más azulada (−)
por zona (frente, mejillas, nariz, mentón), y se compara cada zona con el cambio de TODO el rostro: si
todas cambian igual, lo más probable es la iluminación; si una zona cambia distinto, es un cambio local.

Las «posibles explicaciones» son orientaciones generales sobre lo que suele producir cada tipo de cambio
de color; NO son un diagnóstico (lo dice cada frase y la interfaz).
"""
import cv2
import numpy as np

from services.analisis_colorimetrico import _convertir_a_lab_real
from services.textura import FRENTE, MEJILLAS, NARIZ_T

MENTON = [83, 18, 313, 406, 400, 377, 152, 148, 176, 182]
ZONAS = {
    "frente": ("Frente", FRENTE),
    "mejilla_derecha": ("Mejilla derecha", MEJILLAS["derecha"]),
    "mejilla_izquierda": ("Mejilla izquierda", MEJILLAS["izquierda"]),
    "nariz": ("Nariz", NARIZ_T),
    "menton": ("Mentón", MENTON),
}
UMBRAL = 2.0          # cambio mínimo (unidades L*a*b*) para describir una dirección
ESCALA_MAPA = 8.0     # cambio que se dibuja con el color más intenso


def _mascara(puntos, idx, alto, ancho):
    m = np.zeros((alto, ancho), np.uint8)
    cv2.fillConvexPoly(m, cv2.convexHull(np.array([puntos[i] for i in idx], np.int32)), 255)
    return m == 255


def _hex(lab):
    """Color de muestra (para la interfaz) a partir de L*a*b* reales."""
    L, a, b = lab
    px = np.array([[[L * 255 / 100, a + 128, b + 128]]], np.float32).clip(0, 255).astype(np.uint8)
    bb, g, r = cv2.cvtColor(px, cv2.COLOR_LAB2BGR)[0, 0]
    return f"#{r:02x}{g:02x}{bb:02x}"


def _superponer(base_bgr, color_bgr, intensidad, mascara):
    """Pinta `color_bgr` sobre la foto con opacidad proporcional a `intensidad` (0-1), solo dentro del rostro."""
    alfa = (np.clip(intensidad, 0, 1) * 0.75 * mascara)[..., None]
    return (base_bgr * (1 - alfa) + np.array(color_bgr, np.float32) * alfa).astype(np.uint8)


def analizar(ref_bgr, alineada_bgr, puntos, mascara_rostro) -> dict:
    alto, ancho = ref_bgr.shape[:2]
    lab_r, lab_n = _convertir_a_lab_real(ref_bgr), _convertir_a_lab_real(alineada_bgr)
    rostro = mascara_rostro.astype(bool)
    global_d = (lab_n[rostro].mean(0) - lab_r[rostro].mean(0)).tolist()
    zonas = {}
    for clave, (nombre, idx) in ZONAS.items():
        m = _mascara(puntos, idx, alto, ancho) & rostro
        if m.sum() < 100:
            continue
        r, n = lab_r[m].mean(0), lab_n[m].mean(0)
        d = n - r
        zonas[clave] = {
            "nombre": nombre,
            "lab_referencia": [round(float(v), 2) for v in r], "lab_nueva": [round(float(v), 2) for v in n],
            "color_referencia": _hex(r), "color_nueva": _hex(n),
            "dL": round(float(d[0]), 2), "da": round(float(d[1]), 2), "db": round(float(d[2]), 2),
            "delta_e": round(float(np.linalg.norm(d)), 2),
            # cambio propio de la zona, descontando lo que cambió todo el rostro (luz general)
            "dL_local": round(float(d[0] - global_d[0]), 2), "da_local": round(float(d[1] - global_d[1]), 2),
            "db_local": round(float(d[2] - global_d[2]), 2),
        }
    # Mapas de componentes (suavizados ≈ 1 % del ancho para no dibujar ruido del sensor)
    s = max(1.5, ancho / 100)
    # Se descuenta el cambio general del rostro: los mapas muestran lo LOCAL (el cambio parejo, típico de
    # la luz, ya lo explica el texto) y no tiñen toda la cara cuando la foto salió un poco más oscura.
    dL = cv2.GaussianBlur(lab_n[..., 0] - lab_r[..., 0] - global_d[0], (0, 0), s)
    da = cv2.GaussianBlur(lab_n[..., 1] - lab_r[..., 1] - global_d[1], (0, 0), s)
    f = rostro.astype(np.float32)
    rojez = _superponer(alineada_bgr, (60, 50, 215), da / ESCALA_MAPA, f)          # más roja: rojo
    rojez = _superponer(rojez, (150, 160, 40), -da / ESCALA_MAPA, f)              # menos roja: verde azulado
    luz = _superponer(alineada_bgr, (60, 40, 90), -dL / ESCALA_MAPA, f)           # más oscura: marrón violáceo
    luz = _superponer(luz, (250, 250, 250), dL / ESCALA_MAPA, f)                  # más clara: blanco
    return {
        "global": {"dL": round(global_d[0], 2), "da": round(global_d[1], 2), "db": round(global_d[2], 2)},
        "zonas": zonas,
        "_mapa_rojez": rojez, "_mapa_luz": luz,
    }


def resumen(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def causas(datos: dict) -> list[str]:
    """Posibles explicaciones generales del cambio de color (no diagnóstico)."""
    if not datos or not datos.get("zonas"):
        return []
    g, zonas = datos["global"], list(datos["zonas"].values())
    salida = []
    dls = [z["dL"] for z in zonas]
    if abs(g["dL"]) >= UMBRAL and all(np.sign(v) == np.sign(g["dL"]) for v in dls) and np.std(dls) < abs(g["dL"]) / 2:
        salida.append(f"Todo el rostro se ve {'más claro' if g['dL'] > 0 else 'más oscuro'} de manera pareja: lo más probable es una "
                      "diferencia de luz o de exposición de la cámara entre las fotos, más que un cambio de la piel.")
    if g["db"] >= UMBRAL and abs(g["da"]) < UMBRAL:
        salida.append("Todo el rostro se ve más amarillento: suele deberse a una luz más cálida (lámpara amarilla, sol de la tarde) o a maquillaje.")
    for z in zonas:
        n = z["nombre"].lower()
        if z["da_local"] >= UMBRAL:
            salida.append(f"{z['nombre']}: más enrojecida que el resto. Suele relacionarse con irritación o inflamación de la piel, calor, "
                          "ejercicio o el roce al limpiarla antes de la foto.")
        elif z["da_local"] <= -UMBRAL:
            salida.append(f"{z['nombre']}: menos enrojecida que antes. Puede acompañar la mejoría de un enrojecimiento o una inflamación.")
        if z["dL_local"] <= -UMBRAL and z["db_local"] >= 0:
            salida.append(f"{z['nombre']}: más oscura en esa zona. Puede corresponder a más pigmento (manchas, exposición al sol) "
                          f"o a una sombra sobre la {n}.")
        elif z["dL_local"] >= UMBRAL:
            salida.append(f"{z['nombre']}: más clara en esa zona. Puede ser menos pigmento o un reflejo de luz (brillo) en la {n}.")
    if salida:
        salida.append("Son posibles explicaciones generales según el tipo de cambio de color, no un diagnóstico: confirmalas con el examen clínico.")
    return salida
