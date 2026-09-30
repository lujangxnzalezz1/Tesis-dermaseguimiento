"""Cifrado simétrico para credenciales guardadas en la base (p. ej. contraseña SMTP)."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings


def _fernet() -> Fernet:
    clave = hashlib.sha256(("dermaseguimiento-cifrado|" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(clave))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(cifrado: str) -> str:
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken:
        return ""
