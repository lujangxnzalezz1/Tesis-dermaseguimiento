from datetime import datetime
from typing import Optional

import logging

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from core.config import settings

from core.politica_password import validar_password
from schemas.comunes import limpiar_texto


class UsuarioRegistro(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    confirmar_password: str = Field(max_length=128)
    nombre: str
    acepta_politica: bool
    captcha_token: Optional[str] = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v):
        return limpiar_texto(v, campo="nombre", max_len=100, obligatorio=True)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.lower()
        if settings.VERIFICAR_DOMINIO_EMAIL:
            try:
                validate_email(v, check_deliverability=True)  # consulta los registros DNS (MX) del dominio
            except EmailNotValidError:
                raise ValueError("El dominio del correo no existe o no puede recibir correos. Revisá que esté bien escrito.")
            except Exception:
                logging.getLogger("registro").warning("No se pudo consultar el DNS para %s; se acepta el correo", v)
        return v

    @model_validator(mode="after")
    def _politicas(self):
        if self.password != self.confirmar_password:
            raise ValueError("Las contraseñas no coinciden.")
        validar_password(self.password, self.email)
        if not self.acepta_politica:
            raise ValueError("Tenés que aceptar la Política de Privacidad para crear la cuenta.")
        return self


class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    rol: str
    activo: bool = True
    email_verificado: bool = True


class UsuarioAdminRespuesta(UsuarioRespuesta):
    fecha_creacion: Optional[datetime] = None
    fecha_modificacion: Optional[datetime] = None
    fecha_inactivacion: Optional[datetime] = None
    fecha_reactivacion: Optional[datetime] = None
    motivo_inactivacion: Optional[str] = None
    ultimo_acceso: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    password_vencida: bool = False


class SolicitudReenvio(BaseModel):
    email: EmailStr


class SolicitudRestablecer(BaseModel):
    email: EmailStr


class Restablecer(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(max_length=128)
    confirmar_password: str = Field(max_length=128)

    @model_validator(mode="after")
    def _politicas(self):
        if self.password != self.confirmar_password:
            raise ValueError("Las contraseñas no coinciden.")
        validar_password(self.password)
        return self


class CambiarPassword(BaseModel):
    password_actual: str = Field(max_length=128)
    password: str = Field(max_length=128)
    confirmar_password: str = Field(max_length=128)

    @model_validator(mode="after")
    def _politicas(self):
        if self.password != self.confirmar_password:
            raise ValueError("Las contraseñas no coinciden.")
        validar_password(self.password)
        return self


class CambioEstadoUsuario(BaseModel):
    motivo: Optional[str] = Field(default=None, max_length=300)
    confirmar: bool = False

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, v):
        return limpiar_texto(v, campo="motivo", max_len=300)
