import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.tiempo import ahora
from schemas.comunes import limpiar_texto

_CEDULA = re.compile(r"^\d{4,10}$")
_TELEFONO = re.compile(r"^\+?[0-9][0-9 \-]{5,18}$")
SEXOS = ("F", "M", "O")


def _validar_fecha_nac(v: Optional[date]) -> Optional[date]:
    if v is None:
        return v
    hoy = ahora().date()
    if v > hoy:
        raise ValueError("La fecha de nacimiento no puede ser futura.")
    if v.year < hoy.year - 120:
        raise ValueError("La fecha de nacimiento no es válida.")
    return v


class _Comunes(BaseModel):
    @field_validator("nombre", "apellido", check_fields=False)
    @classmethod
    def _nombres(cls, v, info):
        return limpiar_texto(v, campo=info.field_name, max_len=80, obligatorio=v is not None)

    @field_validator("sexo", check_fields=False)
    @classmethod
    def _sexo(cls, v):
        if v is None or v == "":
            return None
        v = v.strip().upper()
        if v not in SEXOS:
            raise ValueError("El sexo debe ser F, M u O.")
        return v

    @field_validator("telefono", check_fields=False)
    @classmethod
    def _tel(cls, v):
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not _TELEFONO.match(v):
            raise ValueError("El teléfono no tiene un formato válido (solo números, espacios o guiones).")
        return v

    @field_validator("fecha_nacimiento", check_fields=False)
    @classmethod
    def _fnac(cls, v):
        return _validar_fecha_nac(v)

    @field_validator("antecedentes_medicos", "observaciones", check_fields=False)
    @classmethod
    def _texto_largo(cls, v, info):
        return limpiar_texto(v, campo=info.field_name.replace("_", " "), max_len=2000)


class ConsentimientoEntrada(BaseModel):
    acepta: bool
    finalidad: str = Field(
        default="Registro de fotografías clínicas y análisis de la evolución de la piel con fines de seguimiento médico.",
        max_length=500,
    )


class PacienteRegistro(_Comunes):
    cedula: str
    nombre: str
    apellido: str
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    antecedentes_medicos: Optional[str] = None
    observaciones: Optional[str] = None
    consentimiento: ConsentimientoEntrada

    @field_validator("cedula")
    @classmethod
    def _cedula(cls, v):
        v = re.sub(r"[.\s]", "", v or "")
        if not _CEDULA.match(v):
            raise ValueError("La cédula debe contener solo números (entre 4 y 10 dígitos).")
        return v


class PacienteActualizar(_Comunes):
    """Edición con control de concurrencia: `version` debe coincidir con la del servidor."""

    version: int
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    antecedentes_medicos: Optional[str] = None
    observaciones: Optional[str] = None


class PacienteEliminar(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)
    confirmar: bool = False

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, v):
        return limpiar_texto(v, campo="motivo", max_len=300, obligatorio=True)


class PacienteReactivar(BaseModel):
    motivo: Optional[str] = Field(default=None, max_length=300)
    confirmar: bool = False

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, v):
        return limpiar_texto(v, campo="motivo", max_len=300)


class RevocacionConsentimiento(BaseModel):
    motivo: Optional[str] = Field(default=None, max_length=300)

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, v):
        return limpiar_texto(v, campo="motivo", max_len=300)


class PacienteRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cedula: str
    nombre: str
    apellido: str
    fecha_nacimiento: Optional[date]
    sexo: Optional[str]
    telefono: Optional[str]
    antecedentes_medicos: Optional[str]
    observaciones: Optional[str]
    activo: bool = True
    version: int = 1
    tiene_consentimiento: bool = False
    fecha_creacion: Optional[datetime] = None
    eliminado_en: Optional[datetime] = None
    motivo_eliminacion: Optional[str] = None
