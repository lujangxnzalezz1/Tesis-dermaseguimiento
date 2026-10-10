import os
import tempfile

# Configuración de PRUEBA: debe fijarse antes de importar la aplicación.
_TMP = tempfile.mkdtemp(prefix="derma_tests_")
os.environ.update({
    "DATABASE_URL": "sqlite://",
    "SECRET_KEY": "clave-solo-para-pruebas-automaticas-1234567890",
    "PASARELA_WEBHOOK_SECRET": "secreto-pasarela-de-pruebas",
    "RUTA_ALMACENAMIENTO": os.path.join(_TMP, "almacenamiento"),
    "ADMIN_EMAIL": "", "ADMIN_PASSWORD": "",
    "RATE_LIMIT_ENABLED": "false",
    "ENFORCE_SUBSCRIPTION": "true",
    "TRIAL_DAYS": "14",
    "SMTP_ENABLED": "false",
    "VERIFICAR_DOMINIO_EMAIL": "false",   # sin DNS en las pruebas (se prueba aparte, simulado)
    "VERIFICAR_EMAIL_REGISTRO": "false",  # se activa en test_verificacion_email.py
})

import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core import ratelimit  # noqa: E402
from core.database import Base, SessionLocal, engine  # noqa: E402
from core.security import hash_password  # noqa: E402
from main import app  # noqa: E402
from models.usuario import ROL_ADMIN, Usuario  # noqa: E402
from scripts.seed import sembrar  # noqa: E402
from services import pasarela  # noqa: E402

PASSWORD = "Segura#2026ok"


@pytest.fixture(autouse=True)
def base_limpia():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sembrar(db)
    ratelimit.reiniciar()
    shutil.rmtree(os.environ["RUTA_ALMACENAMIENTO"], ignore_errors=True)
    os.makedirs(os.environ["RUTA_ALMACENAMIENTO"], exist_ok=True)
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def datos_registro(email="doc1@example.com", password=PASSWORD, **extra):
    d = {"email": email, "password": password, "confirmar_password": password, "nombre": "Dra. Prueba", "acepta_politica": True}
    d.update(extra)
    return d


def crear_usuario(client, email="doc1@example.com", password=PASSWORD):
    r = client.post("/registro", json=datos_registro(email, password))
    assert r.status_code == 201, r.text
    return r.json()


def login(client, email="doc1@example.com", password=PASSWORD):
    r = client.post("/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def doc(client):
    crear_usuario(client)
    return login(client)


@pytest.fixture
def doc2(client):
    crear_usuario(client, "doc2@example.com")
    return login(client, "doc2@example.com")


@pytest.fixture
def admin(client, db):
    db.add(Usuario(email="admin@example.com", password_hash=hash_password(PASSWORD), nombre="Admin", rol=ROL_ADMIN))
    db.commit()
    return login(client, "admin@example.com")


def datos_paciente(cedula="1234567", **extra):
    d = {"cedula": cedula, "nombre": "Ana", "apellido": "Gómez", "consentimiento": {"acepta": True}}
    d.update(extra)
    return d


def crear_paciente(client, headers, cedula="1234567", **extra):
    r = client.post("/pacientes", json=datos_paciente(cedula, **extra), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def imagen_jpg(semilla=0, tam=(120, 160)):
    rng = np.random.default_rng(semilla)
    img = rng.integers(0, 255, (*tam, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def archivos_seg(a=1, b=2):
    return {
        "imagen_referencia": ("ref.jpg", imagen_jpg(a), "image/jpeg"),
        "imagen_nueva": ("nueva.jpg", imagen_jpg(b), "image/jpeg"),
    }


@pytest.fixture
def pipeline_falso(monkeypatch):
    """Sustituye la detección facial (que requiere un rostro real) por un resultado fijo."""
    def falso(ref, nueva):
        alto, ancho = ref.shape[:2]
        pts = [(10, 10), (ancho - 10, 10), (ancho - 10, alto - 10), (10, alto - 10)] * 120
        return {"exito": True, "imagen_alineada": nueva, "puntos_referencia": pts,
                "cantidad_landmarks_referencia": 478, "cantidad_landmarks_nueva": 478}
    monkeypatch.setattr("routers.procesamiento.procesar_par_de_imagenes", falso)


def firmar_evento(evento: dict, ts=None):
    cuerpo = json.dumps(evento).encode()
    ts = str(int(ts if ts is not None else time.time()))
    return cuerpo, {"Content-Type": "application/json", "X-Pasarela-Timestamp": ts, "X-Pasarela-Firma": pasarela.firmar(cuerpo, ts)}


def webhook(client, pago_ref, estado, monto, moneda="PYG", evento_id="ev1", ts=None):
    cuerpo, cab = firmar_evento({"evento_id": evento_id, "referencia": pago_ref, "estado": estado, "monto": monto, "moneda": moneda,
                                 "forma_pago": "Tarjeta (sandbox)"}, ts)
    return client.post("/webhooks/pago", content=cuerpo, headers=cab)


def pagar(client, headers, plan="premium_mensual", estado="aprobado", evento_id="ev1"):
    r = client.post("/suscripcion/checkout", json={"plan_codigo": plan}, headers=headers)
    assert r.status_code == 200, r.text
    info = r.json()
    ref = info["url_pago"].rsplit("/", 1)[-1]
    return info, webhook(client, ref, estado, info["monto"], info["moneda"], evento_id)
