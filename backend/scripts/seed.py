"""Datos iniciales controlados (punto 27). Es idempotente: se puede ejecutar varias veces.

    python -m scripts.seed
"""
import json
import sys

from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from core.politica_password import errores_password
from core.security import hash_password
from core.tiempo import ahora
from models.configuracion import PlantillaCorreo
from models.suscripcion import Plan
from models.usuario import ROL_ADMIN, Usuario
from services.email_service import PLANTILLAS_POR_DEFECTO

PLANES = [
    dict(codigo="gratuito", nombre="Gratuito", precio=0, periodicidad="gratuito", duracion_dias=0, orden=1,
         incluye_procesamiento=False,
         funcionalidades=["Registro de pacientes y fichas clínicas digitales", "Historial de consultas", "Consulta de información"],
         limites=["Sin procesamiento de imágenes", "Sin reportes de evolución"],
         condiciones="Sin costo ni vencimiento. Podés pasar a Premium cuando quieras."),
    dict(codigo="premium_mensual", nombre="Premium mensual", precio=9.99, periodicidad="mensual", duracion_dias=30, orden=2,
         incluye_procesamiento=True,
         funcionalidades=["Todo lo del plan Gratuito", "Alineación de fotografías con puntos faciales", "Análisis colorimétrico CIE Lab con mapa de calor",
                          "Reportes de evolución ilimitados (CSV)"],
         limites=["Uso profesional individual"],
         condiciones="Cobro cada 30 días (USD). Cancelás cuando quieras y conservás el acceso hasta el fin del período pagado. Sin reembolsos proporcionales."),
    dict(codigo="premium_anual", nombre="Premium anual", precio=79.99, periodicidad="anual", duracion_dias=365, orden=3,
         incluye_procesamiento=True,
         funcionalidades=["Todo lo del plan Premium mensual", "Ahorro frente al pago mensual (aprox. 33 %)"],
         limites=["Uso profesional individual"],
         condiciones="Cobro único por 365 días (USD). Al mejorar desde el mensual se acredita el tiempo no usado. Sin reembolsos proporcionales."),
]


def sembrar(db: Session, admin_email: str = "", admin_password: str = "") -> dict:
    resumen = {"planes": 0, "plantillas": 0, "admin": "no configurado"}
    for p in PLANES:
        fila = db.query(Plan).filter(Plan.codigo == p["codigo"]).first()
        datos = {**p, "funcionalidades": json.dumps(p["funcionalidades"], ensure_ascii=False),
                 "limites": json.dumps(p["limites"], ensure_ascii=False)}
        if fila is None:
            db.add(Plan(**datos))
            resumen["planes"] += 1
        # Los planes existentes NO se sobrescriben: el administrador pudo editarlos.
    for codigo, (asunto, cuerpo) in PLANTILLAS_POR_DEFECTO.items():
        if db.get(PlantillaCorreo, codigo) is None:
            db.add(PlantillaCorreo(codigo=codigo, asunto=asunto, cuerpo=cuerpo))
            resumen["plantillas"] += 1

    if admin_email and admin_password:
        if not db.query(Usuario).filter(Usuario.email == admin_email.lower()).first():
            problemas = errores_password(admin_password, admin_email)
            if problemas:
                raise SystemExit("ADMIN_PASSWORD no cumple la política: " + "; ".join(problemas))
            db.add(Usuario(email=admin_email.lower(), password_hash=hash_password(admin_password), nombre=settings.ADMIN_NOMBRE,
                           rol=ROL_ADMIN, password_cambiada_en=ahora()))
            resumen["admin"] = "creado"
        else:
            resumen["admin"] = "ya existía"
    db.commit()
    return resumen


if __name__ == "__main__":
    with SessionLocal() as sesion:
        print(sembrar(sesion, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD))
    sys.exit(0)
