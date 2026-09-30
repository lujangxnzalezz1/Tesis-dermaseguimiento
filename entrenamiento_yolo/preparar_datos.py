"""Convierte ACNE04 (Hugging Face, Pascal VOC en píxeles) al formato YOLO.

- Usa la partición oficial train/test del conjunto (columna `split`).
- Separa el 10 % de train como validación, estratificado por severidad (semilla fija = reproducible).
- El conjunto de prueba (test) NO se usa en el entrenamiento: sirve solo para las métricas finales.
- Reduce las fotos a 1280 px de lado mayor para acelerar el entrenamiento.

Cita: Wu, X. et al. (2019). Joint Acne Image Grading and Counting via Label Distribution Learning. ICCV.
Licencia de ACNE04: uso académico únicamente.
"""
import glob
import io
import os
import random
from collections import defaultdict

import pyarrow.parquet as pq
from PIL import Image

SALIDA = "datos/acne04_yolo"
LADO_MAX = 1280
random.seed(2026)

filas = []
for f in sorted(glob.glob("datos/acne04_hf/data/*.parquet")):
    filas += pq.read_table(f).to_pylist()
print("imágenes:", len(filas))

por_nivel = defaultdict(list)
for i, r in enumerate(filas):
    if r["split"] == "train":
        por_nivel[r["level"]].append(i)
val = set()
for nivel, idx in por_nivel.items():
    random.shuffle(idx)
    val.update(idx[: max(1, round(len(idx) * 0.10))])

conteo = defaultdict(lambda: [0, 0])
for i, r in enumerate(filas):
    particion = "test" if r["split"] == "test" else ("val" if i in val else "train")
    img = Image.open(io.BytesIO(r["image"]["bytes"])).convert("RGB")
    w, h = img.size
    esc = min(1.0, LADO_MAX / max(w, h))
    if esc < 1:
        img = img.resize((round(w * esc), round(h * esc)), Image.LANCZOS)
    base = os.path.splitext(r["file_name"])[0]
    os.makedirs(f"{SALIDA}/images/{particion}", exist_ok=True)
    os.makedirs(f"{SALIDA}/labels/{particion}", exist_ok=True)
    img.save(f"{SALIDA}/images/{particion}/{base}.jpg", quality=92)
    b = r["lesion_boxes"] or {"xmin": []}
    lineas = []
    for x1, y1, x2, y2 in zip(b["xmin"], b["ymin"], b["xmax"], b["ymax"]):
        x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
        y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        lineas.append(f"0 {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    open(f"{SALIDA}/labels/{particion}/{base}.txt", "w").write("\n".join(lineas))
    conteo[particion][0] += 1
    conteo[particion][1] += len(lineas)

open(f"{SALIDA}/data.yaml", "w").write(
    f"path: {os.path.abspath(SALIDA)}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: lesion_acne\n")
for p, (n, l) in sorted(conteo.items()):
    print(f"{p:5s}: {n} imágenes, {l} lesiones")
