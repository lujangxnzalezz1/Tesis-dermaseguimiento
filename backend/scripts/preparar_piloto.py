"""Prepara la prueba piloto de usabilidad (objetivo 8, escala SUS).

Crea N cuentas de prueba para los dermatólogos participantes, ya confirmadas y con el período de
prueba Premium activo, y a cada una le agrega un «Paciente de demostración» (fotos sintéticas, con
consentimiento) con una consulta ya procesada, para que vean el historial sin usar datos reales.

Las contraseñas se generan al azar y se escriben SOLO en un archivo fuera del repositorio
(por defecto, en el Escritorio), nunca en la base en texto plano ni en la salida.

Uso:
    ./venv/bin/python -m scripts.preparar_piloto --cantidad 5
    ./venv/bin/python -m scripts.preparar_piloto --cantidad 5 --salida ~/Desktop/Piloto_SUS_accesos.md
Si una cuenta ya existe, se le genera una contraseña nueva (y se conserva lo que haya cargado).
"""
import argparse
import os
import secrets
import string
from datetime import datetime

import cv2
from fastapi.testclient import TestClient

from core.config import settings
from core.database import SessionLocal
from core.politica_password import errores_password
from core.security import hash_password
from core.tiempo import ahora
from main import app
from models.usuario import Usuario
from services.suscripcion_service import asegurar_suscripcion

FOTOS = os.path.expanduser("~/Desktop/Tesis_demo_fotos")


def _clave() -> str:
    while True:
        c = (secrets.choice(string.ascii_uppercase) + secrets.choice(string.ascii_lowercase) + secrets.choice(string.digits)
             + secrets.choice("!?#$%") + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8)))
        c = "".join(secrets.SystemRandom().sample(c, len(c)))
        if not errores_password(c):
            return c


def _cuenta(db, n: int) -> tuple[Usuario, str]:
    email = f"piloto{n}@dermaseguimiento.test"
    clave = _clave()
    u = db.query(Usuario).filter(Usuario.email == email).first()
    if u is None:
        u = Usuario(email=email, nombre=f"Participante {n}", password_hash=hash_password(clave), email_verificado=True,
                    email_verificado_en=ahora(), password_cambiada_en=ahora(), politica_aceptada_version=settings.POLITICA_VERSION,
                    politica_aceptada_en=ahora())
        db.add(u)
    else:
        u.password_hash, u.password_cambiada_en, u.intentos_fallidos, u.bloqueado_hasta = hash_password(clave), ahora(), 0, None
    db.commit()
    db.refresh(u)
    asegurar_suscripcion(db, u)
    return u, clave


def _paciente_demo(client: TestClient, email: str, clave: str, n: int) -> None:
    r = client.post("/login", data={"username": email, "password": clave})
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    lista = client.get("/pacientes?q=Demostración", headers=h).json()
    if lista.get("total"):
        return
    p = client.post("/pacientes", headers=h, json={
        "cedula": f"900000{n}", "nombre": "Paciente de", "apellido": "Demostración",
        "observaciones": "Fotos sintéticas para la prueba piloto (no es una persona real).", "consentimiento": {"acepta": True},
    })
    p.raise_for_status()
    leer = lambda f: cv2.imencode(".jpg", cv2.imread(os.path.join(FOTOS, f)))[1].tobytes()  # noqa: E731
    s = client.post("/procesar-seguimiento", headers=h, data={"paciente_id": str(p.json()["id"])}, files={
        "imagen_referencia": ("referencia.jpg", leer("consulta1_referencia.jpg"), "image/jpeg"),
        "imagen_nueva": ("seguimiento.jpg", leer("consulta3_acne.jpg"), "image/jpeg"),
    })
    s.raise_for_status()
    client.post("/logout", headers=h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cantidad", type=int, default=5)
    ap.add_argument("--salida", default=os.path.expanduser("~/Desktop/Piloto_SUS_accesos.md"))
    args = ap.parse_args()
    db = SessionLocal()
    filas = []
    with TestClient(app) as client:
        for n in range(1, args.cantidad + 1):
            u, clave = _cuenta(db, n)
            _paciente_demo(client, u.email, clave, n)
            filas.append((n, u.email, clave))
    db.close()
    with open(args.salida, "w", encoding="utf-8") as f:
        f.write(f"# Prueba piloto DermaSeguimiento — accesos ({datetime.now():%d/%m/%Y %H:%M})\n\n")
        f.write("Entregá UNA cuenta a cada participante. No compartas este archivo.\n\n")
        f.write("| Participante | Correo | Contraseña |\n|---|---|---|\n")
        for n, email, clave in filas:
            f.write(f"| {n} | {email} | `{clave}` |\n")
    print(f"Listo: {len(filas)} cuentas. Accesos guardados en {args.salida}")


if __name__ == "__main__":
    main()
