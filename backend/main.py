import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from core import errores
from core.url_base import fijar_desde_solicitud
from core.config import settings
from routers import (
    admin, admin_planes, admin_seguridad, auth, pacientes, pasarela_sandbox, privacidad, procesamiento, reportes, sus, suscripciones,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# El esquema de la base se gestiona con Alembic:  alembic upgrade head
os.makedirs(settings.RUTA_ALMACENAMIENTO, exist_ok=True)

app = FastAPI(title="DermaSeguimiento API")
errores.instalar(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "Content-Disposition"],
)


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    fijar_desde_solicitud(request.url.scheme, request.headers.get("host"))
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/archivos/"):
        respuesta.headers.setdefault("Cache-Control", "private, max-age=300")
    elif "cache-control" not in respuesta.headers:
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


for r in (auth, privacidad, pacientes, procesamiento, reportes, suscripciones, admin, admin_planes, admin_seguridad, sus):
    app.include_router(r.router)
# Webhook y checkout de prueba: solo existen con PASARELA=sandbox
pasarela_sandbox.incluir_en(app)


@app.get("/")
def read_root():
    return {"mensaje": "API de DermaSeguimiento funcionando correctamente"}


@app.get("/salud")
def salud():
    """Chequeo de disponibilidad para el despliegue. No expone versiones ni datos internos."""
    return {"estado": "ok"}
