from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator

from sqlalchemy.orm import Session

from core.database import get_db
from core.security import obtener_usuario_actual
from models.configuracion import RespuestaSUS
from models.usuario import Usuario
from schemas.comunes import limpiar_texto
from services import auditoria_service as audit

router = APIRouter(tags=["Usabilidad (SUS)"])


def calcular_sus(respuestas: list[int]) -> int:
    """Puntaje SUS estándar: ítems impares (resp-1), pares (5-resp), suma x 2,5."""
    total = sum((r - 1) if i % 2 == 0 else (5 - r) for i, r in enumerate(respuestas))
    return round(total * 2.5)


class EntradaSUS(BaseModel):
    respuestas: list[int] = Field(min_length=10, max_length=10)
    comentario: Optional[str] = Field(default=None, max_length=500)

    @field_validator("respuestas")
    @classmethod
    def _rango(cls, v):
        if any(r < 1 or r > 5 for r in v):
            raise ValueError("Cada respuesta del cuestionario SUS debe estar entre 1 y 5.")
        return v

    @field_validator("comentario")
    @classmethod
    def _c(cls, v):
        return limpiar_texto(v, campo="comentario", max_len=500)


@router.post("/sus", status_code=201)
def registrar_sus(datos: EntradaSUS, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual)):
    puntaje = calcular_sus(datos.respuestas)
    db.add(RespuestaSUS(usuario_id=usuario.id, respuestas=",".join(map(str, datos.respuestas)), puntaje=puntaje, comentario=datos.comentario))
    db.commit()
    audit.registrar(db, request, usuario, "usabilidad", "registrar_sus", despues={"puntaje": puntaje})
    return {"puntaje": puntaje, "mensaje": "¡Gracias por completar el cuestionario!"}
