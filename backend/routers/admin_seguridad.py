"""Configuración de seguridad editable por el administrador: política de contraseñas.

Los valores se guardan en `configuracion_seguridad` (fila única). Si no hay fila se usan las
variables de entorno PASSWORD_*. Todo cambio queda en la auditoría con el antes y el después."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.database import get_db
from core.politica_password import CAMPOS, descripcion_politica, politica_por_defecto, politica_vigente
from core.security import requiere_rol
from core.tiempo import ahora
from models.configuracion import ConfiguracionSeguridad
from models.usuario import ROL_ADMIN, Usuario
from services import auditoria_service as audit

router = APIRouter(prefix="/admin/seguridad", tags=["Administración"])
solo_admin = requiere_rol(ROL_ADMIN)

MAX_COMUNES_ADICIONALES = 500


class PoliticaEntrada(BaseModel):
    longitud_minima: int = Field(ge=8, le=64)  # menos de 8 no es aceptable (NIST SP 800-63B)
    requiere_mayuscula: bool
    requiere_minuscula: bool
    requiere_numero: bool
    requiere_especial: bool
    max_dias_vigencia: int = Field(ge=0, le=730)  # 0 = no vencen
    comunes_adicionales: list[str] = Field(default_factory=list, max_length=MAX_COMUNES_ADICIONALES)

    @field_validator("comunes_adicionales")
    @classmethod
    def _comunes(cls, v):
        limpio = []
        for x in v:
            x = x.strip()
            if not x:
                continue
            if len(x) > 64 or any(c in x for c in "\r\n"):
                raise ValueError("Cada contraseña prohibida debe tener como máximo 64 caracteres y estar en una sola línea.")
            limpio.append(x)
        return sorted(set(limpio))


def _respuesta(db: Session) -> dict:
    pol = politica_vigente(db)
    fila = db.get(ConfiguracionSeguridad, 1)
    return {**pol, "descripcion": descripcion_politica(pol), "valores_entorno": politica_por_defecto(),
            "personalizada": fila is not None, "actualizado_en": fila.actualizado_en if fila else None}


@router.get("/politica-contrasenas")
def ver_politica(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    return _respuesta(db)


@router.put("/politica-contrasenas")
def guardar_politica(datos: PoliticaEntrada, request: Request, db: Session = Depends(get_db),
                     admin: Usuario = Depends(solo_admin)):
    """Las contraseñas existentes no se invalidan: la política nueva se exige en el próximo cambio.
    Si se acorta `max_dias_vigencia`, quienes superen el plazo deberán cambiarla al ingresar."""
    antes = politica_vigente(db)
    fila = db.get(ConfiguracionSeguridad, 1)
    if fila is None:
        fila = ConfiguracionSeguridad(id=1)
        db.add(fila)
    for c in CAMPOS:
        setattr(fila, c, getattr(datos, c))
    fila.comunes_adicionales = "\n".join(datos.comunes_adicionales) or None
    fila.actualizado_en = ahora()
    fila.actualizado_por = admin.id
    db.commit()
    audit.registrar(db, request, admin, "seguridad", "politica_contrasenas", entidad="configuracion_seguridad", entidad_id=1,
                    antes={**antes, "comunes_adicionales": len(antes["comunes_adicionales"])},
                    despues={**datos.model_dump(), "comunes_adicionales": len(datos.comunes_adicionales)})
    return _respuesta(db)


@router.delete("/politica-contrasenas")
def restablecer_politica(request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    """Vuelve a los valores de las variables de entorno."""
    fila = db.get(ConfiguracionSeguridad, 1)
    if fila is not None:
        antes = politica_vigente(db)
        db.delete(fila)
        db.commit()
        audit.registrar(db, request, admin, "seguridad", "politica_contrasenas_restablecer", entidad="configuracion_seguridad",
                        entidad_id=1, antes={**antes, "comunes_adicionales": len(antes["comunes_adicionales"])})
    return _respuesta(db)
