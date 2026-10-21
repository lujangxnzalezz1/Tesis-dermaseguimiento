"""Aplica el plazo de conservación de datos (RETENCION_DATOS_ANIOS, Política de Privacidad).

Por defecto es una SIMULACIÓN: solo cuenta lo que haría. Para aplicar los cambios:

    python -m scripts.retencion_datos            # simulación (no modifica nada)
    python -m scripts.retencion_datos --aplicar  # anonimiza y borra
    python -m scripts.retencion_datos --anios 3  # otro plazo (por defecto el de la configuración)

Pensado para cron (por ejemplo, una vez por mes). Qué hace con lo que superó el plazo:
- Pacientes cuya última consulta (o su alta, si no tienen consultas) es anterior al plazo: se
  reemplazan cédula, nombre, apellido, fecha de nacimiento, teléfono, antecedentes y observaciones,
  y se borran sus fotografías (el rostro identifica a la persona). Las métricas numéricas quedan,
  ya sin forma de vincularlas con nadie.
- Profesionales inactivos desde antes del plazo: se anonimizan como en la baja voluntaria.
- Datos técnicos (sesiones, enlaces de un solo uso, contadores de intentos) de más de
  DIAS_DATOS_TECNICOS días: se eliminan.
No se tocan la auditoría (inmutable, evidencia legal) ni pagos y comprobantes (obligación tributaria)."""
import argparse
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from core.tiempo import ahora
from models.configuracion import IntentoLimitado
from models.paciente import Paciente
from models.seguimiento import Seguimiento
from models.usuario import Sesion, TokenRestablecimiento, Usuario
from services import almacenamiento

DIAS_DATOS_TECNICOS = 90
PREFIJO_ANONIMO = "anon-"


def _columnas_de_imagen():
    return [c for c in Seguimiento.__table__.columns if c.name.startswith("ruta_")]


def _anonimizar_paciente(db: Session, p: Paciente) -> int:
    """Devuelve la cantidad de archivos de imagen borrados."""
    p.cedula = f"{PREFIJO_ANONIMO}{p.id}"
    p.nombre = "Paciente"
    p.apellido = "anonimizado"
    p.fecha_nacimiento = None
    p.telefono = None
    p.antecedentes_medicos = None
    p.observaciones = None
    p.activo = False
    p.eliminado_en = p.eliminado_en or ahora()
    p.motivo_eliminacion = "Plazo de conservación vencido (anonimizado)"
    p.fecha_modificacion = ahora()
    claves = []
    for s in db.query(Seguimiento).filter(Seguimiento.paciente_id == p.id).all():
        for col in _columnas_de_imagen():
            clave = getattr(s, col.name)
            if clave:
                claves.append(clave)
            setattr(s, col.name, None if col.nullable else "")
    almacenamiento.borrar_silencioso(claves)
    return len(claves)


def ejecutar(db: Session, aplicar: bool = False, anios: Optional[int] = None, referencia: Optional[datetime] = None) -> dict:
    from routers.privacidad import anonimizar_usuario  # misma anonimización que la baja voluntaria

    anios = settings.RETENCION_DATOS_ANIOS if anios is None else anios
    referencia = referencia or ahora()
    limite = referencia - timedelta(days=365 * anios)
    limite_tecnico = referencia - timedelta(days=DIAS_DATOS_TECNICOS)

    ultima = (db.query(Seguimiento.paciente_id, func.max(Seguimiento.fecha).label("ultima"))
              .group_by(Seguimiento.paciente_id).subquery())
    pacientes = (
        db.query(Paciente).outerjoin(ultima, ultima.c.paciente_id == Paciente.id)
        .filter(~Paciente.cedula.like(f"{PREFIJO_ANONIMO}%"))
        .filter(func.coalesce(ultima.c.ultima, Paciente.fecha_creacion) < limite)
        .all()
    )
    usuarios = (db.query(Usuario).filter(Usuario.activo.is_(False), Usuario.anonimizado_en.is_(None),
                                         Usuario.fecha_inactivacion.isnot(None), Usuario.fecha_inactivacion < limite).all())
    sesiones = db.query(Sesion).filter(Sesion.expira_en < limite_tecnico)
    tokens = db.query(TokenRestablecimiento).filter(TokenRestablecimiento.expira_en < limite_tecnico)
    intentos = db.query(IntentoLimitado).filter(IntentoLimitado.fecha < limite_tecnico)

    resumen = {
        "modo": "aplicado" if aplicar else "simulacion", "anios": anios, "limite": limite.date().isoformat(),
        "pacientes_anonimizados": len(pacientes), "imagenes_borradas": 0, "usuarios_anonimizados": len(usuarios),
        "sesiones_borradas": sesiones.count(), "tokens_borrados": tokens.count(), "intentos_borrados": intentos.count(),
    }
    if not aplicar:
        resumen["imagenes_borradas"] = sum(
            1 for p in pacientes for s in db.query(Seguimiento).filter(Seguimiento.paciente_id == p.id).all()
            for c in _columnas_de_imagen() if getattr(s, c.name)
        )
        return resumen

    for p in pacientes:
        resumen["imagenes_borradas"] += _anonimizar_paciente(db, p)
    for u in usuarios:
        anonimizar_usuario(db, u, u.motivo_inactivacion or "Plazo de conservación vencido")
    # Las sesiones de usuarios recién anonimizados se revocaron (no se borran si no vencieron)
    sesiones.delete(synchronize_session=False)
    tokens.delete(synchronize_session=False)
    intentos.delete(synchronize_session=False)
    db.commit()

    from services import auditoria_service as audit  # importación diferida: evita ciclos al cargar el script

    audit.registrar(db, None, None, "privacidad", "retencion_datos", despues=resumen)
    return resumen


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description="Aplica el plazo de conservación de datos personales.")
    parser.add_argument("--aplicar", action="store_true", help="aplica los cambios (sin esto, solo simula)")
    parser.add_argument("--anios", type=int, default=None, help=f"plazo en años (por defecto {settings.RETENCION_DATOS_ANIOS})")
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        resumen = ejecutar(db, aplicar=args.aplicar, anios=args.anios)
    print("SIMULACIÓN: no se modificó nada. Usá --aplicar para ejecutar." if not args.aplicar else "Cambios aplicados.")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")
    return resumen


if __name__ == "__main__":
    main()
