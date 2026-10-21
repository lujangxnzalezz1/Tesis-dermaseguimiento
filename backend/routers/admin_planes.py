"""Administración de planes (precio, estado, funcionalidades, límites y condiciones) y reemisión
de comprobantes anulados. Solo administradores; cada cambio queda en la auditoría."""
import json
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import requiere_rol
from models.suscripcion import Plan
from models.usuario import ROL_ADMIN, Usuario
from routers.suscripciones import plan_a_dict
from schemas.comunes import limpiar_texto
from services import auditoria_service as audit
from services import suscripcion_service as svc

router = APIRouter(prefix="/admin", tags=["Administración de planes"])
solo_admin = requiere_rol(ROL_ADMIN)
CAMPOS_PLAN = ["precio", "activo", "funcionalidades", "limites", "condiciones"]
PRECIO_MAXIMO = Decimal("99999999")  # Numeric(10, 2)


def _plan_admin(p: Plan) -> dict:
    return {**plan_a_dict(p), "activo": p.activo, "orden": p.orden}


def _lista(valor: Optional[list[str]], campo: str, minimo: int) -> Optional[list[str]]:
    if valor is None:
        return None
    limpios = [limpiar_texto(v, campo=campo, max_len=200) for v in valor]
    limpios = [v for v in limpios if v]
    if len(limpios) < minimo:
        raise ValueError(f"Agregá al menos {minimo} elemento en «{campo}».")
    if len(set(limpios)) != len(limpios):
        raise ValueError(f"Hay elementos repetidos en «{campo}».")
    return limpios


class PlanEdicion(BaseModel):
    precio: Optional[Decimal] = Field(None, ge=0, le=PRECIO_MAXIMO)
    activo: Optional[bool] = None
    funcionalidades: Optional[list[str]] = Field(None, max_length=20)
    limites: Optional[list[str]] = Field(None, max_length=20)
    condiciones: Optional[str] = Field(None, max_length=1000)

    @field_validator("funcionalidades")
    @classmethod
    def _f(cls, v):
        return _lista(v, "funcionalidades", 1)

    @field_validator("limites")
    @classmethod
    def _l(cls, v):
        return _lista(v, "límites", 0)

    @field_validator("condiciones")
    @classmethod
    def _c(cls, v):
        return limpiar_texto(v, campo="condiciones", max_len=1000, obligatorio=True) if v is not None else None


def _plan(db: Session, codigo: str) -> Plan:
    p = db.query(Plan).filter(Plan.codigo == codigo).first()
    if not p:
        raise HTTPException(404, "No encontramos ese plan.")
    return p


def _foto(p: Plan) -> dict:
    return {"precio": str(p.precio), "activo": p.activo, "funcionalidades": json.loads(p.funcionalidades),
            "limites": json.loads(p.limites), "condiciones": p.condiciones}


@router.get("/planes")
def listar_planes(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    """Todos los planes, también los inactivos (el catálogo público solo muestra los activos)."""
    return {"planes": [_plan_admin(p) for p in db.query(Plan).order_by(Plan.orden).all()]}


@router.patch("/planes/{codigo}")
def editar_plan(codigo: str, datos: PlanEdicion, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    p = _plan(db, codigo)
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(400, "No indicaste ningún cambio.")
    if "condiciones" in cambios and cambios["condiciones"] is None:
        raise HTTPException(422, "Las condiciones no pueden quedar vacías.")
    gratuito = p.periodicidad == "gratuito"
    if cambios.get("precio") is not None:
        precio = cambios["precio"]
        if gratuito and precio != 0:
            raise HTTPException(422, "El plan gratuito no puede tener precio.")
        if not gratuito and precio <= 0:
            raise HTTPException(422, "Un plan pago debe tener un precio mayor que cero. Si no querés ofrecerlo, desactivalo.")
        if p.moneda == "PYG" and precio != precio.to_integral_value():
            raise HTTPException(422, "El guaraní no tiene centavos: ingresá el precio sin decimales.")
    if cambios.get("activo") is False:
        if gratuito:
            raise HTTPException(409, "El plan gratuito no se puede desactivar: es el plan al que vuelven las cuentas sin suscripción.")
        otros = db.query(Plan).filter(Plan.id != p.id, Plan.activo.is_(True), Plan.incluye_procesamiento.is_(True)).count()
        if p.incluye_procesamiento and otros == 0:
            raise HTTPException(409, "Tiene que quedar al menos un plan Premium activo.")

    antes = _foto(p)
    if cambios.get("precio") is not None:
        p.precio = cambios["precio"]
    if cambios.get("activo") is not None:
        p.activo = cambios["activo"]
    if cambios.get("funcionalidades") is not None:
        p.funcionalidades = json.dumps(cambios["funcionalidades"], ensure_ascii=False)
    if "limites" in cambios and cambios["limites"] is not None:
        p.limites = json.dumps(cambios["limites"], ensure_ascii=False)
    if cambios.get("condiciones") is not None:
        p.condiciones = cambios["condiciones"]
    db.commit()
    audit.registrar(db, request, admin, "planes", "editar", entidad="plan", entidad_id=p.codigo, antes=antes, despues=_foto(p))
    return {"mensaje": f"Guardamos los cambios del plan «{p.nombre}». Los pagos ya iniciados mantienen su importe.",
            "plan": _plan_admin(p)}


@router.post("/comprobantes/{cid}/reemitir")
def reemitir_comprobante(cid: int, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    """Emite un comprobante NUEVO (otro número) para el pago de un comprobante anulado; el anulado no cambia."""
    nuevo = svc.reemitir_comprobante(db, cid)
    audit.registrar(db, request, admin, "comprobantes", "reemitir", entidad="comprobante", entidad_id=nuevo.id,
                    despues={"numero": nuevo.numero, "pago_id": nuevo.pago_id, "reemplaza_a": cid})
    return {"mensaje": f"Emitimos el comprobante {nuevo.numero} en reemplazo del anulado.", "id": nuevo.id, "numero": nuevo.numero}
