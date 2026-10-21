"""Registro de auditoría (punto 7 / RNF-12)."""
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from core.security import ip_cliente
from models.auditoria import Auditoria
from models.usuario import Usuario

log = logging.getLogger("auditoria")

CAMPOS_SENSIBLES = {"password", "password_hash", "token", "token_hash", "password_cifrada", "nueva_password"}


def _serializable(valor: Any):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def instantanea(obj, campos: list[str]) -> dict:
    """Foto de un registro (solo los campos indicados) para guardar antes/después."""
    return {c: _serializable(getattr(obj, c, None)) for c in campos if c not in CAMPOS_SENSIBLES}


def _json(datos: Optional[dict]) -> Optional[str]:
    if datos is None:
        return None
    limpio = {k: _serializable(v) for k, v in datos.items() if k not in CAMPOS_SENSIBLES}
    return json.dumps(limpio, ensure_ascii=False, default=str)


def registrar(
    db: Session,
    request: Optional[Request],
    usuario: Optional[Usuario],
    modulo: str,
    accion: str,
    *,
    entidad: Optional[str] = None,
    entidad_id: Any = None,
    antes: Optional[dict] = None,
    despues: Optional[dict] = None,
    resultado: str = "exito",
    detalle: Optional[str] = None,
    email: Optional[str] = None,
    usuario_id: Optional[int] = None,
    confirmar: bool = True,
) -> None:
    """Agrega un registro de auditoría. Con `confirmar=True` hace commit (junto con
    lo que la operación haya dejado pendiente). En rutas de fallo, hacer
    `db.rollback()` antes de llamar para no guardar información incompleta."""
    try:
        db.add(
            Auditoria(
                usuario_id=usuario.id if usuario else usuario_id,
                usuario_email=usuario.email if usuario else email,
                ip=ip_cliente(request) if request is not None else None,
                modulo=modulo,
                accion=accion,
                entidad=entidad,
                entidad_id=str(entidad_id) if entidad_id is not None else None,
                datos_antes=_json(antes),
                datos_despues=_json(despues),
                resultado=resultado,
                detalle=(detalle or "")[:500] or None,
            )
        )
        if confirmar:
            db.commit()
    except Exception:  # la auditoría nunca debe romper la operación principal
        log.exception("No se pudo registrar el evento de auditoría %s/%s", modulo, accion)
        db.rollback()


def registrar_fallo(db: Session, request, usuario, modulo: str, accion: str, detalle: str, **kw) -> None:
    db.rollback()
    registrar(db, request, usuario, modulo, accion, resultado="fallo", detalle=detalle, **kw)
