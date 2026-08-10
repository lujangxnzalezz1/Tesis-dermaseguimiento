from datetime import date
from typing import Optional

from pydantic import BaseModel


class PacienteRegistro(BaseModel):
    cedula: str
    nombre: str
    apellido: str
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    antecedentes_medicos: Optional[str] = None
    observaciones: Optional[str] = None


class PacienteRespuesta(BaseModel):
    id: int
    cedula: str
    nombre: str
    apellido: str
    fecha_nacimiento: Optional[date]
    sexo: Optional[str]
    telefono: Optional[str]
    antecedentes_medicos: Optional[str]
    observaciones: Optional[str]

    class Config:
        from_attributes = True
