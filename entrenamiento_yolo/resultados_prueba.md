# Detección de lesiones de acné — YOLOv8n entrenado con ACNE04

## Datos
- Conjunto: ACNE04 (Wu et al., 2019, ICCV). 1.457 imágenes faciales, 18.983 lesiones anotadas. Licencia: uso académico.
- Partición: oficial train/test del conjunto; 10 % de train separado como validación, estratificado por severidad (semilla 2026).
- Una sola clase («lesión de acné»): el modelo localiza regiones, no clasifica el tipo de lesión ni diagnostica.

## Entrenamiento
- Modelo base: YOLOv8n preentrenado en COCO (transferencia de aprendizaje), entrada 1024 px.
- Épocas ejecutadas: 51 (máximo 100, detención temprana con paciencia 25). Hardware: Apple M4 Pro (MPS).

## Resultados en el conjunto de PRUEBA (292 imágenes nunca vistas en el entrenamiento)
| Métrica | Valor |
|---|---|
| mAP@0,5 | 0.292 |
| mAP@0,5:0,95 | 0.074 |
| Precisión | 0.411 |
| Exhaustividad (recall) | 0.344 |
| F1 | 0.374 |
| Tiempo de inferencia por imagen (CPU) | 71 ms |

Gráficos (curva PR, matriz de confusión, ejemplos): `/Users/lujan.gonzalez/Desktop/Tesis/runs/detect/runs/acne_yolov8n/prueba/`

## Limitaciones
- ACNE04 proviene de pacientes de otra población; el desempeño en fototipos de pacientes de Asunción no está validado.
- Las lesiones muy pequeñas o poco contrastadas son las más difíciles de detectar (ver curva PR).
- Licencia académica: para un uso comercial del sistema (plan Premium) se requiere autorización de los autores o reentrenar con datos propios.
