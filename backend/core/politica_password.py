"""Política de contraseñas (punto 5).

Los parámetros se leen de la tabla `configuracion_seguridad` (editable por el administrador en
/admin/seguridad/politica-contrasenas) y, si no hay fila o un campo está vacío, de las variables
de entorno PASSWORD_*. Además de las reglas de composición se rechazan contraseñas comunes,
secuencias (123456, abcdef, qwerty), caracteres repetidos y las que contienen el nombre del correo."""
import logging
import re
from typing import Optional

from core.config import settings

log = logging.getLogger("politica_password")

# Lista curada de las contraseñas más usadas (filtraciones públicas: listas de SplashData/NordPass,
# RockYou y "10k most common") más variantes locales. Se comparan normalizadas (minúsculas, sin
# símbolos y sin números), así "Dragon2024!" cuenta como "dragon".
_COMUNES = {
    # números y teclados
    "123456", "12345678", "123456789", "1234567890", "12345678910", "1234567", "12345", "1234", "123123", "123321",
    "654321", "666666", "111111", "000000", "121212", "112233", "123qwe", "qwe123", "1q2w3e", "1q2w3e4r", "1q2w3e4r5t",
    "1qaz2wsx", "zaq12wsx", "qazwsx", "qwerty", "qwerty123", "qwertyuiop", "asdfgh", "asdfghjkl", "zxcvbn", "zxcvbnm",
    "azerty", "qwertz", "a1b2c3", "abc123", "abcd1234", "aa123456", "q1w2e3r4", "147258369", "159753", "987654321",
    "789456", "456789", "741852963", "142536", "131313", "696969", "777777", "888888", "999999", "555555",
    # palabras en inglés
    "password", "passw0rd", "password1", "password123", "pass", "pass123", "letmein", "welcome", "welcome1", "iloveyou",
    "monkey", "dragon", "master", "shadow", "sunshine", "princess", "football", "baseball", "soccer", "hockey",
    "superman", "batman", "spiderman", "trustno1", "starwars", "whatever", "freedom", "michael", "jennifer", "jordan",
    "charlie", "michelle", "jessica", "ashley", "daniel", "thomas", "robert", "hunter", "ranger", "buster", "tigger",
    "jordan23", "harley", "andrew", "joshua", "matthew", "pepper", "ginger", "cheese", "summer", "winter", "secret",
    "computer", "internet", "killer", "love", "lovely", "loveme", "hello", "hello123", "flower", "cookie", "chocolate",
    "maggie", "taylor", "bailey", "access", "mustang", "corvette", "ferrari", "liverpool", "chelsea", "arsenal",
    "samsung", "apple", "google", "facebook", "linkedin", "twitter", "instagram", "youtube", "microsoft", "nintendo",
    "pokemon", "minecraft", "fortnite", "login", "admin", "admin123", "administrator", "root", "toor", "guest",
    "user", "test", "test123", "demo", "default", "changeme", "qwerty1", "abc", "temp", "temporal", "system",
    "server", "oracle", "mysql", "postgres", "database", "letmein1", "money", "silver", "golden", "diamond",
    "orange", "banana", "purple", "yellow", "blue", "red", "green", "black", "white", "angel", "angels", "blessed",
    "family", "forever", "friends", "jesus", "christ", "heaven", "god", "lucky", "magic", "music", "rockyou", "babygirl",
    "sweet", "sweetheart", "honey", "baby", "123abc", "mother", "father", "doctor", "hospital", "health", "medical",
    # palabras en español y locales
    "contraseña", "contrasena", "clave", "clave123", "miclave", "micontraseña", "secreto", "hola", "hola123",
    "holamundo", "bienvenido", "bienvenida", "teamo", "teamo123", "tequiero", "amor", "amormio", "corazon", "princesa",
    "mariposa", "estrella", "angelito", "chocolate", "tesoro", "familia", "dios", "diosesamor", "jesucristo", "futbol",
    "barcelona", "realmadrid", "boca", "bocajuniors", "river", "riverplate", "olimpia", "cerroporteño", "cerroporteno",
    "libertad", "guarani", "albirroja", "paraguay", "asuncion", "encarnacion", "ciudaddeleste", "luque", "sanlorenzo",
    "lambare", "fernandodelamora", "capiata", "mariano", "maria", "jose", "juan", "carlos", "luis", "ana", "sofia",
    "valentina", "camila", "lucia", "martina", "santiago", "mateo", "sebastian", "alejandro", "gabriel", "fernando",
    "argentina", "brasil", "mexico", "colombia", "españa", "espana", "uruguay", "chile", "peru", "bolivia",
    "doctora", "medico", "medica", "dermatologia", "dermatologo", "dermatologa", "consultorio", "clinica", "paciente",
    "salud", "piel", "dermaseguimiento", "derma", "unida", "unida2026", "usuario", "administrador", "prueba",
    "pruebas", "invitado", "sistema", "acceso", "ingresar", "entrar", "cambiar", "cambiame", "nueva", "nuevaclave",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
    "diciembre", "lunes", "verano", "invierno", "primavera", "otoño", "otono",
}

_norm = lambda t: re.sub(r"[^a-z0-9ñ]", "", t.lower())  # noqa: E731
_COMUNES_NORM = {_norm(c) for c in _COMUNES}
_ESPECIALES = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~¡¿€£¥·")

# Filas de teclado y alfabeto para detectar secuencias (en ambos sentidos)
_SECUENCIAS = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl", "zxcvbnm", "1qaz2wsx3edc")
_LARGO_SECUENCIA = 5   # 5 o más caracteres seguidos de una secuencia: "12345", "abcde", "qwert"
_LARGO_REPETICION = 4  # 4 o más veces el mismo carácter: "aaaa", "1111"

CAMPOS = ("longitud_minima", "requiere_mayuscula", "requiere_minuscula", "requiere_numero", "requiere_especial",
          "max_dias_vigencia")


def politica_por_defecto() -> dict:
    return {
        "longitud_minima": settings.PASSWORD_MIN_LENGTH,
        "requiere_mayuscula": settings.PASSWORD_REQUIRE_UPPER,
        "requiere_minuscula": settings.PASSWORD_REQUIRE_LOWER,
        "requiere_numero": settings.PASSWORD_REQUIRE_DIGIT,
        "requiere_especial": settings.PASSWORD_REQUIRE_SPECIAL,
        "max_dias_vigencia": settings.PASSWORD_MAX_AGE_DAYS,
        "comunes_adicionales": [],
    }


def politica_vigente(db=None) -> dict:
    """Valores efectivos: los de la base (si el admin los cambió) y, para lo que falte, los del entorno.
    Si la base no responde se usan los del entorno: nunca se deja de validar."""
    pol = politica_por_defecto()
    from core.database import SessionLocal  # importación diferida: evita ciclos al arrancar
    from models.configuracion import ConfiguracionSeguridad

    propia = db is None
    sesion = SessionLocal() if propia else db
    try:
        fila = sesion.get(ConfiguracionSeguridad, 1)
        if fila:
            for c in CAMPOS:
                if getattr(fila, c) is not None:
                    pol[c] = getattr(fila, c)
            pol["comunes_adicionales"] = [x.strip() for x in (fila.comunes_adicionales or "").splitlines() if x.strip()]
    except Exception:
        log.exception("No se pudo leer la política de contraseñas de la base; se usan los valores del entorno")
    finally:
        if propia:
            sesion.close()
    return pol


def descripcion_politica(pol: Optional[dict] = None) -> str:
    pol = pol or politica_vigente()
    partes = [f"al menos {pol['longitud_minima']} caracteres"]
    if pol["requiere_mayuscula"]:
        partes.append("una mayúscula")
    if pol["requiere_minuscula"]:
        partes.append("una minúscula")
    if pol["requiere_numero"]:
        partes.append("un número")
    if pol["requiere_especial"]:
        partes.append("un carácter especial (por ejemplo ! ? # $ %)")
    return ("La contraseña debe tener " + ", ".join(partes) + ". No puede ser una contraseña común, una secuencia "
            "(123456, abcdef) ni contener tu correo.")


def _tiene_secuencia(texto: str) -> bool:
    t = texto.lower()
    for base in _SECUENCIAS:
        for s in (base, base[::-1]):
            for i in range(len(s) - _LARGO_SECUENCIA + 1):
                if s[i:i + _LARGO_SECUENCIA] in t:
                    return True
    return False


def _tiene_repeticion(texto: str) -> bool:
    return re.search(r"(.)\1{%d,}" % (_LARGO_REPETICION - 1), texto.lower()) is not None


def _es_comun(password: str, adicionales: list[str]) -> bool:
    n = _norm(password)
    # también sin los números: «Dragon2024!» o «2024Dragon» cuentan como «dragon»
    candidatos = {n, n.rstrip("0123456789"), n.lstrip("0123456789"), re.sub(r"\d", "", n)}
    prohibidas = _COMUNES_NORM | {_norm(a) for a in adicionales}
    return bool(candidatos & prohibidas) or n.rstrip("0123456789") == ""  # solo números


def errores_password(password: str, email: str | None = None, pol: Optional[dict] = None) -> list[str]:
    pol = pol or politica_vigente()
    errores = []
    if len(password) < pol["longitud_minima"]:
        errores.append(f"debe tener al menos {pol['longitud_minima']} caracteres")
    if len(password) > 128:
        errores.append("no puede superar los 128 caracteres")
    if pol["requiere_mayuscula"] and not any(c.isupper() for c in password):
        errores.append("debe incluir una letra mayúscula")
    if pol["requiere_minuscula"] and not any(c.islower() for c in password):
        errores.append("debe incluir una letra minúscula")
    if pol["requiere_numero"] and not any(c.isdigit() for c in password):
        errores.append("debe incluir un número")
    if pol["requiere_especial"] and not any(c in _ESPECIALES for c in password):
        errores.append("debe incluir un carácter especial (por ejemplo ! ? # $ %)")
    if _es_comun(password, pol["comunes_adicionales"]):
        errores.append("es demasiado común o predecible")
    if _tiene_secuencia(password):
        errores.append("no debe contener secuencias como 12345, abcde o qwert")
    if _tiene_repeticion(password):
        errores.append(f"no debe repetir el mismo carácter {_LARGO_REPETICION} o más veces seguidas")
    if email:
        local = email.split("@")[0].lower()
        partes = {local, *[p for p in re.split(r"[._\-+]", local)]}
        if any(len(p) >= 4 and p in password.lower() for p in partes):
            errores.append("no debe contener tu correo electrónico ni partes de él")
    return errores


def validar_password(password: str, email: str | None = None) -> str:
    errores = errores_password(password, email)
    if errores:
        raise ValueError("La contraseña " + "; ".join(errores) + ".")
    return password
