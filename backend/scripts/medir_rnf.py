"""Mide el cumplimiento de RNF-06 (procesamiento <= 5 s por par de imágenes) con fotos reales.

    python -m scripts.medir_rnf foto_referencia.jpg foto_nueva.jpg [repeticiones]
"""
import statistics
import sys
import time

import cv2

from core.config import settings
from services.analisis_colorimetrico import analizar_color
from services.procesamiento_imagenes import procesar_par_de_imagenes


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    ref, nueva = cv2.imread(sys.argv[1]), cv2.imread(sys.argv[2])
    if ref is None or nueva is None:
        raise SystemExit("No se pudo leer alguna de las imágenes.")
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    tiempos = []
    for _ in range(n):
        t = time.perf_counter()
        r = procesar_par_de_imagenes(ref, nueva)
        if not r["exito"]:
            raise SystemExit(r["error"])
        analizar_color(ref, r["imagen_alineada"], r["puntos_referencia"])
        tiempos.append(time.perf_counter() - t)
    limite = settings.TIEMPO_MAXIMO_PROCESAMIENTO_SEGUNDOS
    p95 = sorted(tiempos)[max(0, int(len(tiempos) * 0.95) - 1)]
    print(f"Repeticiones: {n}  mín {min(tiempos):.2f}s  mediana {statistics.median(tiempos):.2f}s  p95 {p95:.2f}s  máx {max(tiempos):.2f}s")
    print(f"RNF-06 (<= {limite}s): {'CUMPLE' if max(tiempos) <= limite else 'NO CUMPLE'}")


if __name__ == "__main__":
    main()
