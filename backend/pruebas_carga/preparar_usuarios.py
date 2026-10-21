"""Crea las cuentas de la prueba de carga (cargaNN@example.com), confirmadas y con pacientes de ejemplo.

    python -m pruebas_carga.preparar_usuarios --cantidad 50 --pacientes 30

Usar SOLO contra una base de prueba. Es idempotente: si la cuenta existe, se le restablece la contraseña.
La contraseña se toma de CARGA_PASSWORD (la misma que usa locustfile.py).
"""
import argparse
import os

from core.config import settings
from core.database import SessionLocal
from core.security import hash_password
from core.tiempo import ahora
from models.paciente import ConsentimientoPaciente, Paciente
from models.usuario import Usuario
from services.suscripcion_service import asegurar_suscripcion

PASSWORD = os.environ.get("CARGA_PASSWORD", "Carga#2026segura")


def preparar(cantidad: int, pacientes: int) -> None:
    clave = hash_password(PASSWORD)  # bcrypt es lento: se calcula una sola vez
    with SessionLocal() as db:
        for n in range(1, cantidad + 1):
            email = f"carga{n:02d}@example.com"
            u = db.query(Usuario).filter(Usuario.email == email).first()
            if u is None:
                u = Usuario(email=email, nombre=f"Carga {n:02d}", password_hash=clave, email_verificado=True,
                            password_cambiada_en=ahora(), politica_aceptada_version=settings.POLITICA_VERSION, politica_aceptada_en=ahora())
                db.add(u)
                db.flush()
                for i in range(pacientes):
                    p = Paciente(cedula=f"{n:02d}{i:05d}", nombre=f"Paciente{i}", apellido=f"Carga{n:02d}", dermatologo_id=u.id)
                    db.add(p)
                    db.flush()
                    db.add(ConsentimientoPaciente(paciente_id=p.id, registrado_por=u.id, version_politica=settings.POLITICA_VERSION,
                                                  finalidad="Prueba de carga"))
            else:
                u.password_hash, u.intentos_fallidos, u.bloqueado_hasta, u.activo = clave, 0, None, True
            db.commit()
            asegurar_suscripcion(db, u)
    print(f"Listo: {cantidad} cuentas cargaNN@example.com con {pacientes} pacientes cada una.")


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Prepara las cuentas para la prueba de carga.")
    a.add_argument("--cantidad", type=int, default=50)
    a.add_argument("--pacientes", type=int, default=30)
    args = a.parse_args()
    preparar(args.cantidad, args.pacientes)
