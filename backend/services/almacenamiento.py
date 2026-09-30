"""Almacenamiento y validación de imágenes (punto 22 / RNF-21 / RNF-02)."""
import hashlib
import os
import uuid

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile

from core.config import settings

EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp"}
TIPOS = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
_FIRMAS = [(b"\xff\xd8\xff", "jpeg"), (b"\x89PNG\r\n\x1a\n", "png")]


def _formato_real(cabecera: bytes):
    for firma, nombre in _FIRMAS:
        if cabecera.startswith(firma):
            return nombre
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "webp"
    return None


def leer_imagen_validada(archivo: UploadFile, etiqueta: str):
    """Valida tipo declarado, extensión, tamaño y CONTENIDO REAL. Devuelve (imagen_bgr, sha256)."""
    nombre = (archivo.filename or "").lower()
    ext = os.path.splitext(nombre)[1]
    if ext and ext not in EXTENSIONES:
        raise HTTPException(400, f"La {etiqueta} tiene un formato no permitido. Usá una foto JPG, PNG o WEBP.")
    if archivo.content_type and archivo.content_type.lower() not in TIPOS:
        raise HTTPException(400, f"La {etiqueta} no es una imagen válida. Usá una foto JPG, PNG o WEBP.")

    limite = settings.MAX_UPLOAD_MB * 1024 * 1024
    contenido = archivo.file.read(limite + 1)
    if len(contenido) > limite:
        raise HTTPException(413, f"La {etiqueta} pesa más de {settings.MAX_UPLOAD_MB} MB. Sacá la foto con menor resolución o comprimila.")
    if not contenido:
        raise HTTPException(400, f"La {etiqueta} está vacía. Elegí la foto de nuevo.")
    if _formato_real(contenido[:16]) is None:
        raise HTTPException(400, f"El archivo de la {etiqueta} no es una imagen JPG, PNG o WEBP real, aunque su nombre lo aparente.")

    imagen = cv2.imdecode(np.frombuffer(contenido, np.uint8), cv2.IMREAD_COLOR)
    if imagen is None:
        raise HTTPException(400, f"No pudimos leer la {etiqueta}: el archivo está dañado. Volvé a tomar o elegir la foto.")
    if imagen.shape[0] * imagen.shape[1] > settings.MAX_IMAGE_PIXELS:
        raise HTTPException(413, f"La {etiqueta} tiene una resolución demasiado grande. Usá una foto de menor tamaño.")
    return imagen, hashlib.sha256(contenido).hexdigest()


def nueva_clave() -> str:
    """Clave opaca y aleatoria: no revela paciente, fecha ni datos personales."""
    u = uuid.uuid4().hex
    return f"imagenes/{u[:2]}/{u}.jpg"


def ruta_absoluta(clave: str) -> str:
    base = os.path.realpath(settings.RUTA_ALMACENAMIENTO)
    destino = os.path.realpath(os.path.join(base, clave))
    if not destino.startswith(base + os.sep):
        raise HTTPException(404, "No encontramos el archivo pedido.")
    return destino


def guardar_imagen(imagen: np.ndarray, clave: str) -> None:
    destino = ruta_absoluta(clave)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if not cv2.imwrite(destino, imagen):
        raise OSError("No se pudo escribir la imagen en disco")


def borrar_silencioso(claves: list[str]) -> None:
    for c in claves:
        try:
            os.remove(ruta_absoluta(c))
        except Exception:
            pass
