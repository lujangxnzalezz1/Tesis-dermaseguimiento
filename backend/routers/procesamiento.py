import base64

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from core.security import obtener_usuario_actual
from models.usuario import Usuario
from services.procesamiento_imagenes import procesar_par_de_imagenes

router = APIRouter(tags=["Procesamiento de imágenes"])


def _leer_imagen_desde_upload(archivo: UploadFile) -> np.ndarray:
    """Convierte un archivo subido (UploadFile) en una imagen que OpenCV
    pueda procesar (formato BGR, el que usa OpenCV internamente)."""
    contenido = archivo.file.read()
    arreglo_bytes = np.frombuffer(contenido, np.uint8)
    imagen = cv2.imdecode(arreglo_bytes, cv2.IMREAD_COLOR)
    return imagen


def _imagen_a_base64(imagen: np.ndarray) -> str:
    """Convierte una imagen de OpenCV a texto base64, para poder
    devolverla dentro de una respuesta JSON."""
    _, buffer = cv2.imencode(".jpg", imagen)
    return base64.b64encode(buffer).decode("utf-8")


@router.post("/procesar-seguimiento")
def procesar_seguimiento(
    imagen_referencia: UploadFile = File(...),
    imagen_nueva: UploadFile = File(...),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """RF-09, RF-10, RF-11: recibe dos fotografías (la de referencia y la
    nueva captura de seguimiento), detecta los puntos anatómicos faciales
    y alinea geométricamente la nueva imagen con la de referencia."""

    ref_bgr = _leer_imagen_desde_upload(imagen_referencia)
    nueva_bgr = _leer_imagen_desde_upload(imagen_nueva)

    if ref_bgr is None or nueva_bgr is None:
        raise HTTPException(status_code=400, detail="No se pudo leer una de las imágenes enviadas.")

    resultado = procesar_par_de_imagenes(ref_bgr, nueva_bgr)

    if not resultado["exito"]:
        raise HTTPException(status_code=422, detail=resultado["error"])

    imagen_base64 = _imagen_a_base64(resultado["imagen_alineada"])

    return {
        "mensaje": "Imagen alineada correctamente",
        "landmarks_detectados_referencia": resultado["cantidad_landmarks_referencia"],
        "landmarks_detectados_nueva": resultado["cantidad_landmarks_nueva"],
        "imagen_alineada_base64": imagen_base64,
    }
