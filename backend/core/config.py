import os

DATABASE_URL = "postgresql://lujan.gonzalez@localhost:5432/dermaseguimiento"

SECRET_KEY = "cambiar-esto-por-una-clave-secreta-real-antes-de-produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Carpeta donde se guardan las imágenes de los seguimientos (referencia,
# nueva captura y resultado alineado), organizadas por paciente.
RUTA_ALMACENAMIENTO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "almacenamiento")
