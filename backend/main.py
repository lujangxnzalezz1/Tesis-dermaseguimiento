import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from core.config import RUTA_ALMACENAMIENTO
from core.database import Base, engine
from models import Usuario, Paciente, Seguimiento  # noqa: F401 - registran las tablas en Base.metadata
from routers import auth, pacientes, procesamiento

Base.metadata.create_all(bind=engine)

os.makedirs(RUTA_ALMACENAMIENTO, exist_ok=True)

app = FastAPI(title="DermaSeguimiento API")

app.include_router(auth.router)
app.include_router(pacientes.router)
app.include_router(procesamiento.router)
app.mount("/archivos", StaticFiles(directory=RUTA_ALMACENAMIENTO), name="archivos")


@app.get("/")
def read_root():
    return {"mensaje": "API de DermaSeguimiento funcionando correctamente"}


@app.get("/test-db")
def test_db_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        version = result.fetchone()[0]
    return {"conexion": "exitosa", "version_postgresql": version}
