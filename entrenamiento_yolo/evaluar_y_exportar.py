"""Evaluación final en el conjunto de PRUEBA (nunca visto en el entrenamiento) y exportación a ONNX.

    ./venv/bin/python evaluar_y_exportar.py
Genera `resultados_prueba.md` (métricas para el Capítulo V) y copia el modelo al backend.
"""
import glob
import json
import os
import shutil
import time

from ultralytics import YOLO

CORRIDA = sorted(glob.glob(os.path.expanduser("~/Desktop/Tesis/runs/detect/runs/acne_yolov8n*")))[-1]
PESOS = os.path.join(CORRIDA, "weights", "best.pt")
DATOS = "datos/acne04_yolo/data.yaml"
IMGSZ = 1024
DESTINO = os.path.expanduser("~/Desktop/Tesis/backend/modelos/acne_yolov8n.onnx")

modelo = YOLO(PESOS)
m = modelo.val(data=DATOS, split="test", imgsz=IMGSZ, batch=8, device="cpu", plots=True, project=CORRIDA, name="prueba", exist_ok=True)
p, r = float(m.box.mp), float(m.box.mr)
f1 = 2 * p * r / (p + r) if p + r else 0.0

# Tiempo de inferencia en CPU (como correría en el servidor)
imgs = sorted(glob.glob("datos/acne04_yolo/images/test/*.jpg"))[:30]
t0 = time.perf_counter()
for im in imgs:
    modelo.predict(im, imgsz=IMGSZ, device="cpu", verbose=False)
ms = (time.perf_counter() - t0) / len(imgs) * 1000

onnx = modelo.export(format="onnx", imgsz=IMGSZ, opset=12)
os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
shutil.copy(onnx, DESTINO)

resumen = {"mAP50": round(float(m.box.map50), 4), "mAP50_95": round(float(m.box.map), 4), "precision": round(p, 4),
           "recall": round(r, 4), "f1": round(f1, 4), "inferencia_cpu_ms": round(ms, 1), "imagenes_prueba": len(glob.glob("datos/acne04_yolo/images/test/*.jpg"))}
json.dump(resumen, open("resultados_prueba.json", "w"), indent=2)
args = open(os.path.join(CORRIDA, "args.yaml")).read()
epocas = sum(1 for _ in open(os.path.join(CORRIDA, "results.csv"))) - 1
open("resultados_prueba.md", "w").write(f"""# Detección de lesiones de acné — YOLOv8n entrenado con ACNE04

## Datos
- Conjunto: ACNE04 (Wu et al., 2019, ICCV). 1.457 imágenes faciales, 18.983 lesiones anotadas. Licencia: uso académico.
- Partición: oficial train/test del conjunto; 10 % de train separado como validación, estratificado por severidad (semilla 2026).
- Una sola clase («lesión de acné»): el modelo localiza regiones, no clasifica el tipo de lesión ni diagnostica.

## Entrenamiento
- Modelo base: YOLOv8n preentrenado en COCO (transferencia de aprendizaje), entrada {IMGSZ} px.
- Épocas ejecutadas: {epocas} (máximo 100, detención temprana con paciencia 25). Hardware: Apple M4 Pro (MPS).

## Resultados en el conjunto de PRUEBA ({resumen['imagenes_prueba']} imágenes nunca vistas en el entrenamiento)
| Métrica | Valor |
|---|---|
| mAP@0,5 | {resumen['mAP50']:.3f} |
| mAP@0,5:0,95 | {resumen['mAP50_95']:.3f} |
| Precisión | {resumen['precision']:.3f} |
| Exhaustividad (recall) | {resumen['recall']:.3f} |
| F1 | {resumen['f1']:.3f} |
| Tiempo de inferencia por imagen (CPU) | {resumen['inferencia_cpu_ms']:.0f} ms |

Gráficos (curva PR, matriz de confusión, ejemplos): `{CORRIDA}/prueba/`

## Limitaciones
- ACNE04 proviene de pacientes de otra población; el desempeño en fototipos de pacientes de Asunción no está validado.
- Las lesiones muy pequeñas o poco contrastadas son las más difíciles de detectar (ver curva PR).
- Licencia académica: para un uso comercial del sistema (plan Premium) se requiere autorización de los autores o reentrenar con datos propios.
""")
print(json.dumps(resumen, indent=2))
print("Modelo copiado a", DESTINO)
