"""Validación del módulo de alineación (objetivo específico 7).

Para cada par (referencia, nueva) mide ANTES y DESPUÉS de alinear:
  - Error de alineación: distancia promedio entre los 468 puntos faciales correspondientes de la
    referencia y de la otra foto, dividida por la distancia entre los ojos de la referencia (error
    normalizado, sin unidades; 0 = coincidencia perfecta).
  - SSIM sobre la región del rostro (mayor = más parecidas).
Criterio de aceptación (sección 3.8): reducción del error ≥ 70 % en al menos el 80 % de los pares.

Fuentes de pares:
  --semisinteticos N  : N pares a partir de N rostros distintos del conjunto ACNE04; la foto «nueva»
                        es la misma con giro, escala, desplazamiento, luz y desenfoque conocidos
                        (simula tomar la foto otro día con otro encuadre).
  --carpeta RUTA      : pares reales: archivos <nombre>_a.jpg (referencia) y <nombre>_b.jpg (nueva).
Salida: tabla CSV por par y resumen en Markdown (por defecto en backend/resultados_validacion/).

Uso: ./venv/bin/python -m scripts.validar_alineacion --semisinteticos 50 [--carpeta ~/Desktop/pares_reales]
"""
import argparse
import csv
import glob
import os
import random
import statistics

import cv2
import numpy as np

from services.analisis_colorimetrico import _calcular_mascara_rostro
from services.procesamiento_imagenes import detectar_landmarks, procesar_par_de_imagenes
from services.similitud import ssim

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACNE04 = os.path.join(BASE, "..", "entrenamiento_yolo", "datos", "acne04_yolo", "images")
OJOS = (33, 263)  # comisuras externas


def _error(p_ref, p_otra) -> float:
    a, b = np.array(p_ref, float), np.array(p_otra, float)
    n = min(len(a), len(b), 468)
    interocular = np.linalg.norm(a[OJOS[0]] - a[OJOS[1]])
    return float(np.linalg.norm(a[:n] - b[:n], axis=1).mean() / interocular)


def medir_par(ref, nueva) -> dict | None:
    alto, ancho = ref.shape[:2]
    nueva = cv2.resize(nueva, (ancho, alto)) if nueva.shape[:2] != ref.shape[:2] else nueva
    p_ref, p_nueva = detectar_landmarks(ref), detectar_landmarks(nueva)
    if p_ref is None or p_nueva is None:
        return None
    r = procesar_par_de_imagenes(ref, nueva)
    if not r["exito"]:
        return None
    p_alin = detectar_landmarks(r["imagen_alineada"])
    if p_alin is None:
        return None
    mascara = _calcular_mascara_rostro(p_ref, alto, ancho) == 255
    e_antes, e_despues = _error(p_ref, p_nueva), _error(p_ref, p_alin)
    return {
        "error_antes": round(e_antes, 4), "error_despues": round(e_despues, 4),
        "reduccion_pct": round(100 * (e_antes - e_despues) / e_antes, 1) if e_antes > 0 else 0.0,
        "ssim_antes": round(ssim(ref, nueva, mascara), 4), "ssim_despues": round(ssim(ref, r["imagen_alineada"], mascara), 4),
    }


def _perturbar(img, rng: random.Random):
    """Otra «toma» del mismo rostro: giro ±12°, escala 0,85-1,15, desplazamiento ±8 %, luz ±15 %, desenfoque leve."""
    alto, ancho = img.shape[:2]
    ang, esc = rng.uniform(-12, 12), rng.uniform(0.85, 1.15)
    m = cv2.getRotationMatrix2D((ancho / 2, alto / 2), ang, esc)
    m[0, 2] += rng.uniform(-0.08, 0.08) * ancho
    m[1, 2] += rng.uniform(-0.08, 0.08) * alto
    out = cv2.warpAffine(img, m, (ancho, alto), borderMode=cv2.BORDER_REPLICATE)
    out = cv2.convertScaleAbs(out, alpha=rng.uniform(0.85, 1.15), beta=rng.uniform(-12, 12))
    if rng.random() < 0.5:
        out = cv2.GaussianBlur(out, (0, 0), rng.uniform(0.5, 1.2))
    return out, {"giro": round(ang, 1), "escala": round(esc, 3)}


def pares_semisinteticos(n: int, semilla: int = 2026):
    rng = random.Random(semilla)
    archivos = sorted(glob.glob(os.path.join(ACNE04, "*", "*.jpg")))
    rng.shuffle(archivos)
    usados = 0
    for f in archivos:
        if usados >= n:
            break
        ref = cv2.imread(f)
        if ref is None or detectar_landmarks(ref) is None:
            continue  # sin rostro completo detectable: no sirve como referencia
        nueva, params = _perturbar(ref, rng)
        usados += 1
        yield os.path.basename(f), "semisintético", ref, nueva, params


def pares_reales(carpeta: str):
    for a in sorted(glob.glob(os.path.join(os.path.expanduser(carpeta), "*_a.*"))):
        b = glob.glob(a.rsplit("_a.", 1)[0] + "_b.*")
        if b:
            yield os.path.basename(a).rsplit("_a.", 1)[0], "real", cv2.imread(a), cv2.imread(b[0]), {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semisinteticos", type=int, default=50)
    ap.add_argument("--carpeta", default=None)
    ap.add_argument("--salida", default=os.path.join(BASE, "resultados_validacion"))
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    filas, descartados = [], 0
    # Semisintéticos: se generan candidatos hasta tener N pares válidos (los descartes se informan aparte:
    # son casos en que el rostro transformado quedó fuera de cuadro o no se detectaron sus puntos).
    validos_semi = 0
    for nombre, tipo, ref, nueva, params in pares_semisinteticos(args.semisinteticos * 3):
        if validos_semi >= args.semisinteticos:
            break
        m = medir_par(ref, nueva)
        if m is None:
            descartados += 1
            continue
        filas.append({"par": nombre, "tipo": tipo, **params, **m})
        validos_semi += 1
    for nombre, tipo, ref, nueva, params in (pares_reales(args.carpeta) if args.carpeta else []):
        m = medir_par(ref, nueva)
        if m is None:
            descartados += 1
            continue
        filas.append({"par": nombre, "tipo": tipo, **params, **m})
    with open(os.path.join(args.salida, "validacion_alineacion.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["par", "tipo", "giro", "escala", "error_antes", "error_despues", "reduccion_pct", "ssim_antes", "ssim_despues"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    red = [r["reduccion_pct"] for r in filas]
    cumplen = sum(1 for x in red if x >= 70)
    sa, sd = [r["ssim_antes"] for r in filas], [r["ssim_despues"] for r in filas]
    resumen = {
        "pares_validos": len(filas), "descartados": descartados,
        "error_antes_media": round(statistics.mean(r["error_antes"] for r in filas), 4),
        "error_despues_media": round(statistics.mean(r["error_despues"] for r in filas), 4),
        "reduccion_media_pct": round(statistics.mean(red), 1), "reduccion_mediana_pct": round(statistics.median(red), 1),
        "pares_con_reduccion_70": cumplen, "pct_pares_con_reduccion_70": round(100 * cumplen / len(filas), 1),
        "ssim_antes_media": round(statistics.mean(sa), 4), "ssim_despues_media": round(statistics.mean(sd), 4),
        "pares_con_ssim_mayor": sum(1 for a, d in zip(sa, sd) if d > a),
    }
    with open(os.path.join(args.salida, "validacion_alineacion.md"), "w", encoding="utf-8") as f:
        f.write("# Validación de la alineación (objetivo 7)\n\n")
        for k, v in resumen.items():
            f.write(f"- {k}: {v}\n")
    print(resumen)


if __name__ == "__main__":
    main()
