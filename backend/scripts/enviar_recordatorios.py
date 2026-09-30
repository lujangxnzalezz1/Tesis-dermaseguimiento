"""Avisos de vencimiento para todos los usuarios activos. Pensado para cron (una vez al día):

    0 9 * * *  cd /ruta/backend && ./venv/bin/python -m scripts.enviar_recordatorios
"""
from core.database import SessionLocal
from models.usuario import Usuario
from services.suscripcion_service import generar_avisos

if __name__ == "__main__":
    with SessionLocal() as db:
        total = sum(len(generar_avisos(db, u)) for u in db.query(Usuario).filter(Usuario.activo.is_(True)).all())
    print(f"Avisos generados: {total}")
