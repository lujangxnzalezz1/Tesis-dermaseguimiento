import os
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.config import RUTA_ALMACENAMIENTO
from core.database import get_db
from core.security import obtener_usuario_actual
from models.paciente import Paciente
from models.seguimiento import Seguimiento
from models.usuario import Usuario
from schemas.seguimiento import SeguimientoRespuesta
from services.analisis_colorimetrico import analizar_color
from services.procesamiento_imagenes import procesar_par_de_imagenes

router = APIRouter(tags=["Procesamiento de imágenes"])


def _leer_imagen_desde_upload(archivo: UploadFile) -> np.ndarray:
    """Convierte un archivo subido (UploadFile) en una imagen que OpenCV
    pueda procesar (formato BGR, el que usa OpenCV internamente)."""
    contenido = archivo.file.read()
    arreglo_bytes = np.frombuffer(contenido, np.uint8)
    imagen = cv2.imdecode(arreglo_bytes, cv2.IMREAD_COLOR)
    return imagen


def _guardar_imagen(imagen: np.ndarray, ruta_absoluta: str) -> None:
    os.makedirs(os.path.dirname(ruta_absoluta), exist_ok=True)
    cv2.imwrite(ruta_absoluta, imagen)


def _a_respuesta(seguimiento: Seguimiento) -> SeguimientoRespuesta:
    return SeguimientoRespuesta(
        id=seguimiento.id,
        paciente_id=seguimiento.paciente_id,
        fecha=seguimiento.fecha,
        landmarks_referencia=seguimiento.landmarks_referencia,
        landmarks_nueva=seguimiento.landmarks_nueva,
        url_imagen_referencia=f"/archivos/{seguimiento.ruta_imagen_referencia}",
        url_imagen_nueva=f"/archivos/{seguimiento.ruta_imagen_nueva}",
        url_imagen_alineada=f"/archivos/{seguimiento.ruta_imagen_alineada}",
        delta_e_promedio=seguimiento.delta_e_promedio,
        l_referencia=seguimiento.l_referencia,
        a_referencia=seguimiento.a_referencia,
        b_referencia=seguimiento.b_referencia,
        l_nueva=seguimiento.l_nueva,
        a_nueva=seguimiento.a_nueva,
        b_nueva=seguimiento.b_nueva,
        url_mapa_calor=f"/archivos/{seguimiento.ruta_mapa_calor}",
    )


@router.post("/procesar-seguimiento", response_model=SeguimientoRespuesta)
def procesar_seguimiento(
    paciente_id: int = Form(...),
    imagen_referencia: UploadFile = File(...),
    imagen_nueva: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """RF-09, RF-10, RF-11: recibe dos fotografías (la de referencia y la
    nueva captura de seguimiento), detecta los puntos anatómicos faciales,
    alinea geométricamente la nueva imagen con la de referencia, analiza
    el cambio de color de piel en espacio CIE L*a*b* y guarda todo el
    resultado en el historial del paciente."""

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    ref_bgr = _leer_imagen_desde_upload(imagen_referencia)
    nueva_bgr = _leer_imagen_desde_upload(imagen_nueva)

    if ref_bgr is None or nueva_bgr is None:
        raise HTTPException(status_code=400, detail="No se pudo leer una de las imágenes enviadas.")

    resultado = procesar_par_de_imagenes(ref_bgr, nueva_bgr)

    if not resultado["exito"]:
        raise HTTPException(status_code=422, detail=resultado["error"])

    analisis_color = analizar_color(
        ref_bgr, resultado["imagen_alineada"], resultado["puntos_referencia"]
    )

    if not analisis_color["exito"]:
        raise HTTPException(status_code=422, detail=analisis_color["error"])

    fecha = datetime.utcnow()
    prefijo = fecha.strftime("%Y%m%d_%H%M%S_%f")
    carpeta_relativa = os.path.join("seguimientos", str(paciente_id))

    ruta_referencia = os.path.join(carpeta_relativa, f"{prefijo}_referencia.jpg")
    ruta_nueva = os.path.join(carpeta_relativa, f"{prefijo}_nueva.jpg")
    ruta_alineada = os.path.join(carpeta_relativa, f"{prefijo}_alineada.jpg")
    ruta_mapa_calor = os.path.join(carpeta_relativa, f"{prefijo}_mapa_calor.jpg")

    _guardar_imagen(ref_bgr, os.path.join(RUTA_ALMACENAMIENTO, ruta_referencia))
    _guardar_imagen(nueva_bgr, os.path.join(RUTA_ALMACENAMIENTO, ruta_nueva))
    _guardar_imagen(resultado["imagen_alineada"], os.path.join(RUTA_ALMACENAMIENTO, ruta_alineada))
    _guardar_imagen(analisis_color["mapa_calor"], os.path.join(RUTA_ALMACENAMIENTO, ruta_mapa_calor))

    nuevo_seguimiento = Seguimiento(
        paciente_id=paciente_id,
        usuario_id=usuario_actual.id,
        fecha=fecha,
        ruta_imagen_referencia=ruta_referencia,
        ruta_imagen_nueva=ruta_nueva,
        ruta_imagen_alineada=ruta_alineada,
        landmarks_referencia=resultado["cantidad_landmarks_referencia"],
        landmarks_nueva=resultado["cantidad_landmarks_nueva"],
        ruta_mapa_calor=ruta_mapa_calor,
        delta_e_promedio=analisis_color["delta_e_promedio"],
        l_referencia=analisis_color["l_referencia"],
        a_referencia=analisis_color["a_referencia"],
        b_referencia=analisis_color["b_referencia"],
        l_nueva=analisis_color["l_nueva"],
        a_nueva=analisis_color["a_nueva"],
        b_nueva=analisis_color["b_nueva"],
    )
    db.add(nuevo_seguimiento)
    db.commit()
    db.refresh(nuevo_seguimiento)

    return _a_respuesta(nuevo_seguimiento)


@router.get("/pacientes/{paciente_id}/seguimientos", response_model=list[SeguimientoRespuesta])
def listar_seguimientos(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Historial de seguimientos de un paciente, del más reciente al más antiguo."""
    seguimientos = (
        db.query(Seguimiento)
        .filter(Seguimiento.paciente_id == paciente_id)
        .order_by(Seguimiento.fecha.desc())
        .all()
    )

    return [_a_respuesta(s) for s in seguimientos]
