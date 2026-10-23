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

    # --- Seguridad: CAPTCHA, límite de frecuencia y proxies ---
    # CAPTCHA: turnstile (Cloudflare) | hcaptcha | recaptcha. Si CAPTCHA_SECRET está vacío queda desactivado.
    CAPTCHA_PROVIDER: str = "turnstile"
    CAPTCHA_SECRET: str = ""
    CAPTCHA_SITE_KEY: str = ""        # clave pública: la app la obtiene de GET /config-publica
    CAPTCHA_VERIFY_URL: str = ""      # vacío = la URL oficial del proveedor elegido
    CAPTCHA_PUNTAJE_MINIMO: float = 0.5  # solo reCAPTCHA v3 (que devuelve un puntaje de 0 a 1)
    # La app nativa muestra el CAPTCHA en una vista web (react-native-webview). Con true, el servidor
    # acepta sin CAPTCHA las solicitudes que llegan con la cabecera «X-Cliente: app-nativa». La cabecera
    # se puede falsificar: activarlo deja como protección solo el límite de frecuencia y el bloqueo de cuenta.
    CAPTCHA_EXIMIR_APP_NATIVA: bool = False
    # Límite de frecuencia: "base" guarda los intentos en la base (sirve con varios procesos); "memoria" no.
    RATE_LIMIT_BACKEND: str = "base"
    # IPs o redes (CIDR) de los proxies inversos de confianza, separadas por coma. Solo si la conexión
    # viene de uno de ellos se lee la IP real de X-Forwarded-For / X-Real-IP. Vacío = no se confía en nadie.
    TRUSTED_PROXIES: str = ""
    # Política de privacidad: finalidad que se registra con el consentimiento del profesional
    FINALIDAD_CONSENTIMIENTO_USUARIO: str = "uso del sistema"

    # --- Verificación del correo electrónico ---
    VERIFICAR_DOMINIO_EMAIL: bool = True     # consulta DNS: el dominio debe existir y poder recibir correos
    VERIFICAR_EMAIL_REGISTRO: bool = True    # la cuenta nueva no puede ingresar hasta confirmar el correo
    VERIFICACION_EMAIL_HORAS: int = 24

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

    # --- Detección de lesiones de acné (RF-14 / RF-15) ---
    RUTA_MODELO_ACNE: str = os.path.join(_BASE_DIR, "modelos", "acne_yolov8n.onnx")
    ACNE_IMGSZ: int = 1024              # tamaño de entrada con el que se entrenó el modelo
    ACNE_CONFIANZA_MIN: float = 0.25
    ACNE_IOU_NMS: float = 0.5
    ACNE_IOU_MISMA_LESION: float = 0.1  # solapamiento mínimo para considerar que es la misma lesión

    # --- Interpretación en lenguaje natural (umbrales de percepción del color, CIE76) ---
    # 2,3 ≈ diferencia mínima perceptible (Sharma, 2003). No son umbrales clínicos validados.
    INTERP_DELTA_E_PERCEPTIBLE: float = 2.3
    INTERP_DELTA_E_MODERADO: float = 5.0
    INTERP_DELTA_E_MARCADO: float = 10.0
    INTERP_UMBRAL_COMPONENTE: float = 1.5   # cambio mínimo en L*, a* o b* para describir una dirección
    INTERP_UMBRAL_OJERAS: float = 1.5       # cambio mínimo en el contraste de ojeras
    INTERP_UMBRAL_MANCHAS_PCT: float = 0.5  # cambio mínimo en el % de piel con manchas (puntos porcentuales)

    # --- Manchas (zonas más oscuras que la piel de alrededor) ---
    MANCHAS_UMBRAL_RELATIVO: float = 0.10  # una zona cuenta si es al menos un 10 % más oscura (L*) que su entorno
    MANCHAS_ELONGACION_MAX: float = 3.0     # más alargada que esto = surco o pliegue, no mancha
    MANCHAS_ESCALA_FONDO: float = 0.10  # radio del entorno de comparación / ancho del rostro
    MANCHAS_AREA_MIN: float = 0.0004    # área mínima de una mancha / área de piel analizada (descarta poros y ruido)
    MANCHAS_MARGEN_BORDE: float = 0.05  # borde del rostro que no se analiza (pelo, sombra del contorno)

    # --- Textura: líneas/arrugas, poros y brillo de la zona T ---
    TEXTURA_UMBRAL_FRANGI: float = 0.08       # respuesta mínima del filtro de Frangi para contar como línea
    TEXTURA_LARGO_MIN_LINEA_MM: float = 3.0   # descarta marcas cortas (no son líneas)
    TEXTURA_PX_POR_MM_POROS: float = 10.0     # detalle mínimo de la foto para medir poros
    TEXTURA_UMBRAL_POROS: float = 0.04        # cuánto más oscuro (L* relativa) que su entorno debe ser un poro
    TEXTURA_BRILLO_L_RELATIVO: float = 0.12   # reflejo: al menos 12 % más claro que la mediana de la zona T
    UV_TONO_MAX: int = 22                     # fluorescencia de porfirinas: tono rojo-anaranjado (0-22 en OpenCV)
    UV_SATURACION_MIN: int = 120
    UV_RESALTE_MIN: int = 35                  # cuánto más brillante que su entorno (0-255)
    INTERP_UMBRAL_LINEAS: float = 2.5        # cambio mínimo (mm/cm²) para describir más o menos líneas
    INTERP_UMBRAL_POROS: float = 5.0          # cambio mínimo en poros por cm²
    INTERP_UMBRAL_BRILLO: float = 1.0         # cambio mínimo en % de brillo de la zona T

    # --- Guía de captura (RF-03): umbrales del control de calidad de la foto ---
    CAPTURA_ANCHO_ROSTRO_MIN: float = 0.35   # ancho del rostro / ancho de la foto
    CAPTURA_ANCHO_ROSTRO_MAX: float = 0.80
    CAPTURA_DESCENTRADO_MAX: float = 0.12    # distancia de la nariz al centro / tamaño de la foto
    CAPTURA_INCLINACION_MAX_GRADOS: float = 8.0
    CAPTURA_GIRO_MAX: float = 0.12           # asimetría horizontal de la nariz (0 = de frente)
    CAPTURA_LUZ_MIN: float = 35.0            # L* promedio del rostro (0-100)
    CAPTURA_LUZ_MAX: float = 85.0
    CAPTURA_SOBREEXPUESTO_MAX: float = 0.05  # fracción de píxeles del rostro quemados
    CAPTURA_NITIDEZ_MIN: float = 25.0        # varianza del Laplaciano sobre el rostro normalizado
    CAPTURA_DIF_ESCALA_MAX: float = 0.15     # diferencia de tamaño del rostro con la referencia
    CAPTURA_DIF_LUZ_MAX: float = 5.0         # diferencia de L* con la referencia

    # --- Privacidad ---
    POLITICA_VERSION: str = "1.0"
    RESPONSABLE_TRATAMIENTO: str = "Luján Esmeralda González López (UNIDA)"
    CONTACTO_PRIVACIDAD: str = ""  # obligatorio en producción (.env): correo para ejercer derechos
    RETENCION_DATOS_ANIOS: int = 5

    # --- Suscripciones y pagos ---
    ENFORCE_SUBSCRIPTION: bool = True
    TRIAL_DAYS: int = 14
    AVISOS_DIAS_ANTES: str = "7,3,1"
    PASARELA: str = "sandbox"
    PASARELA_WEBHOOK_SECRET: str = Field(min_length=16)  # obligatorio: sin valor por defecto conocido
    PASARELA_WEBHOOK_TOLERANCIA_SEGUNDOS: int = 300
    # AdamsPay (PASARELA=adamspay). Pruebas: staging; producción: https://checkout.adamspay.com/api/v1
    ADAMSPAY_API_URL: str = "https://staging.adamspay.com/api/v1"
    ADAMSPAY_API_KEY: str = ""
    BASE_URL: str = "http://localhost:8000"
    # Orígenes web permitidos (versión web de la app). Separados por coma.
    CORS_ORIGINS: str = "http://localhost:8081,http://127.0.0.1:8081"
    # Además se permite la app web servida desde cualquier IP de red privada (para abrirla desde el celular)
    CORS_ORIGIN_REGEX: str = (r"(http://(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):8081"
                              r"|https://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):8443)")
    EMISOR_NOMBRE: str = "DermaSeguimiento"
    EMISOR_RUC: str = ""
    EMISOR_EMAIL: str = ""  # correo que figura en los comprobantes (.env)

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

    # --- Notificaciones push (OneSignal; sin clave no se envían) ---
    ONESIGNAL_APP_ID: str = ""
    ONESIGNAL_REST_API_KEY: str = ""
    ONESIGNAL_TIMEOUT_SECONDS: int = 10

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

    # --- Pagos y planes ---
    ADAMSPAY_TIMEOUT_SEGUNDOS: int = 15       # espera máxima de cada llamada al API de AdamsPay
    ADAMSPAY_VIGENCIA_HORAS: int = 24         # validez de la deuda: pasado este plazo ya no se puede pagar
    EMISOR_LOGO_RUTA: str = ""                # imagen (PNG/JPG) del logo del emisor en el recibo; vacío = sin logo
    COMPROBANTE_ENLACE_MINUTOS: int = 5       # validez del enlace de descarga del recibo (app nativa)

    # Límites de los listados y exportaciones
    MAX_PLANTILLAS: int = 50          # plantillas de indicaciones por profesional
    MAX_FILAS_CSV: int = 20000        # filas máximas del CSV de auditoría


settings = Settings()

# Compatibilidad con módulos que importaban las constantes sueltas.
DATABASE_URL = settings.DATABASE_URL
RUTA_ALMACENAMIENTO = settings.RUTA_ALMACENAMIENTO
