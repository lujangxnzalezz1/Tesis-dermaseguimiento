"""Política de contraseñas (punto 5). Todos los parámetros vienen de la configuración."""
import re

from core.config import settings

_COMUNES = {
    "123456", "12345678", "123456789", "1234567890", "password", "password1", "contraseña",
    "contrasena", "qwerty", "qwerty123", "abc123", "111111", "000000", "admin", "admin123",
    "letmein", "welcome", "iloveyou", "monkey", "dragon", "123123", "654321", "1q2w3e4r",
    "password123", "paraguay", "asuncion", "dermaseguimiento", "unida2026", "12345678910",
}
_norm = lambda t: re.sub(r"[^a-z0-9ñ]", "", t.lower())  # noqa: E731
_COMUNES_NORM = {_norm(c) for c in _COMUNES}
_ESPECIALES = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~¡¿€£¥·")


def descripcion_politica() -> str:
    partes = [f"al menos {settings.PASSWORD_MIN_LENGTH} caracteres"]
    if settings.PASSWORD_REQUIRE_UPPER:
        partes.append("una mayúscula")
    if settings.PASSWORD_REQUIRE_LOWER:
        partes.append("una minúscula")
    if settings.PASSWORD_REQUIRE_DIGIT:
        partes.append("un número")
    if settings.PASSWORD_REQUIRE_SPECIAL:
        partes.append("un carácter especial (por ejemplo ! ? # $ %)")
    return "La contraseña debe tener " + ", ".join(partes) + "."


def errores_password(password: str, email: str | None = None) -> list[str]:
    errores = []
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errores.append(f"debe tener al menos {settings.PASSWORD_MIN_LENGTH} caracteres")
    if len(password) > 128:
        errores.append("no puede superar los 128 caracteres")
    if settings.PASSWORD_REQUIRE_UPPER and not any(c.isupper() for c in password):
        errores.append("debe incluir una letra mayúscula")
    if settings.PASSWORD_REQUIRE_LOWER and not any(c.islower() for c in password):
        errores.append("debe incluir una letra minúscula")
    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        errores.append("debe incluir un número")
    if settings.PASSWORD_REQUIRE_SPECIAL and not any(c in _ESPECIALES for c in password):
        errores.append("debe incluir un carácter especial (por ejemplo ! ? # $ %)")
    if _norm(password) in _COMUNES_NORM or _norm(password).rstrip("0123456789") in _COMUNES_NORM:
        errores.append("es demasiado común o predecible")
    if email:
        local = email.split("@")[0].lower()
        if len(local) >= 4 and local in password.lower():
            errores.append("no debe contener tu correo electrónico")
    return errores


def validar_password(password: str, email: str | None = None) -> str:
    errores = errores_password(password, email)
    if errores:
        raise ValueError("La contraseña " + "; ".join(errores) + ".")
    return password
