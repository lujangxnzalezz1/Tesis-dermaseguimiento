"""Configuración central del sistema.

Todos los valores que pueden cambiar con el tiempo (expiración de sesión,
política de contraseñas, límites, precios de prueba, etc.) se leen de
variables de entorno o del archivo `.env` (ver `.env.example`). Nada
sensible queda escrito en el código fuente.
"""
import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(_BASE_DIR, ".env"), extra="ignore"
    )

    # --- Base de datos y secretos (obligatorios, sin valor por defecto) ---
    DATABASE_URL: str
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"

    # --- Sesiones ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    INACTIVITY_TIMEOUT_MINUTES: int = 30

    # --- Política de contraseñas (configurable) ---
    PASSWORD_MIN_LENGTH: int = 10
    PASSWORD_REQUIRE_UPPER: bool = True
    PASSWORD_REQUIRE_LOWER: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    PASSWORD_MAX_AGE_DAYS: int = 0  # 0 = las contraseñas no vencen

    # --- Protección contra abuso ---
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_MAX: int = 10  # peticiones por ventana y por IP (login/registro)
    RATE_LIMIT_AUTH_WINDOW_SECONDS: int = 60
    CAPTCHA_SECRET: str = ""  # si está vacío, el CAPTCHA queda desactivado
    CAPTCHA_VERIFY_URL: str = "https://www.google.com/recaptcha/api/siteverify"

    # --- Recuperación de contraseña ---
    RESET_TOKEN_MINUTES: int = 10
    FRONTEND_URL: str = "dermaseguimiento://restablecer"

    # --- Archivos ---
    MAX_UPLOAD_MB: int = 10
    MAX_IMAGE_PIXELS: int = 40_000_000
    RUTA_ALMACENAMIENTO: str = os.path.join(_BASE_DIR, "almacenamiento")

    # --- Procesamiento de imágenes ---
    DELTA_E_MAXIMO_VISUAL: float = 30.0
    TIEMPO_MAXIMO_PROCESAMIENTO_SEGUNDOS: float = 5.0  # RNF-06 (se mide y se audita)

    # --- Privacidad ---
    POLITICA_VERSION: str = "1.0"
    RESPONSABLE_TRATAMIENTO: str = "Luján Esmeralda González López (UNIDA)"
    CONTACTO_PRIVACIDAD: str = "lujangxnzalezz1@gmail.com"
    RETENCION_DATOS_ANIOS: int = 5

    # --- Suscripciones y pagos ---
    ENFORCE_SUBSCRIPTION: bool = True
    TRIAL_DAYS: int = 14
    AVISOS_DIAS_ANTES: str = "7,3,1"
    PASARELA: str = "sandbox"
    PASARELA_WEBHOOK_SECRET: str = Field(min_length=16)  # obligatorio: sin valor por defecto conocido
    PASARELA_WEBHOOK_TOLERANCIA_SEGUNDOS: int = 300
    BASE_URL: str = "http://localhost:8000"
    EMISOR_NOMBRE: str = "DermaSeguimiento"
    EMISOR_RUC: str = ""
    EMISOR_EMAIL: str = "lujangxnzalezz1@gmail.com"

    # --- Correo (valores por defecto; se pueden sobrescribir desde la API de administración) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_SECURITY: str = "starttls"  # none | starttls | ssl
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@dermaseguimiento.local"
    SMTP_FROM_NAME: str = "DermaSeguimiento"
    SMTP_TIMEOUT_SECONDS: int = 10
    SMTP_ENABLED: bool = False

    # --- Datos iniciales (script `python -m scripts.seed`) ---
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_NOMBRE: str = "Administrador"

    @field_validator("AVISOS_DIAS_ANTES")
    @classmethod
    def _validar_avisos(cls, valor: str) -> str:
        [int(x) for x in valor.split(",") if x.strip()]
        return valor

    @property
    def avisos_dias(self) -> list[int]:
        return sorted({int(x) for x in self.AVISOS_DIAS_ANTES.split(",") if x.strip()}, reverse=True)


settings = Settings()

# Compatibilidad con módulos que importaban las constantes sueltas.
DATABASE_URL = settings.DATABASE_URL
RUTA_ALMACENAMIENTO = settings.RUTA_ALMACENAMIENTO
