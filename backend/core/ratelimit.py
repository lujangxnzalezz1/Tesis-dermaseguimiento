"""Limitador de frecuencia por IP (punto 0).

Con RATE_LIMIT_BACKEND=base los intentos se guardan en la tabla `intentos_limitados`, así el
límite se respeta aunque el servidor corra con varios procesos o se reinicie. Si la base falla
(o con RATE_LIMIT_BACKEND=memoria) se usa un contador en memoria del proceso.

La IP se obtiene con `ip_cliente` (solo confía en X-Forwarded-For si viene de un proxy listado en
TRUSTED_PROXIES). Cada rechazo con 429 queda en la auditoría."""
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import ip_cliente
from core.tiempo import ahora

log = logging.getLogger("ratelimit")

_eventos: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def reiniciar():
    with _lock:
        _eventos.clear()


def _parametros(maximo, ventana) -> tuple[int, int]:
    return maximo or settings.RATE_LIMIT_AUTH_MAX, ventana or settings.RATE_LIMIT_AUTH_WINDOW_SECONDS


def _clave(request: Request, nombre: str) -> str:
    return f"{nombre}:{ip_cliente(request) or 'desconocida'}"


# ------------------------------------------------------------------ contador en memoria

def _memoria_espera(clave: str, maximo: int, ventana: int) -> int:
    """Segundos que faltan para poder intentar de nuevo (0 = puede intentar)."""
    ahora_ = time.monotonic()
    with _lock:
        cola = _eventos[clave]
        while cola and cola[0] <= ahora_ - ventana:
            cola.popleft()
        if len(cola) >= maximo:
            return int(ventana - (ahora_ - cola[0])) + 1
    return 0


def _memoria_anotar(clave: str) -> None:
    with _lock:
        _eventos[clave].append(time.monotonic())


# ------------------------------------------------------------------ contador en la base

def _base_espera(db: Session, clave: str, maximo: int, ventana: int) -> int:
    from models.configuracion import IntentoLimitado

    desde = ahora() - timedelta(seconds=ventana)
    consulta = db.query(IntentoLimitado).filter(IntentoLimitado.clave == clave, IntentoLimitado.fecha > desde)
    if consulta.count() < maximo:
        return 0
    primero = consulta.order_by(IntentoLimitado.fecha).first()
    return int(ventana - (ahora() - primero.fecha).total_seconds()) + 1


def _base_anotar(db: Session, clave: str, ventana: int) -> None:
    from models.configuracion import IntentoLimitado

    # Se borran los intentos de esta clave que ya salieron de la ventana: la tabla no crece sin límite
    db.query(IntentoLimitado).filter(
        IntentoLimitado.clave == clave, IntentoLimitado.fecha <= ahora() - timedelta(seconds=ventana)
    ).delete(synchronize_session=False)
    db.add(IntentoLimitado(clave=clave, fecha=ahora()))
    db.commit()


def _usar_base(db) -> bool:
    return db is not None and settings.RATE_LIMIT_BACKEND == "base"


def _espera(db, clave, maximo, ventana) -> int:
    if _usar_base(db):
        try:
            return _base_espera(db, clave, maximo, ventana)
        except Exception:
            log.exception("Límite de frecuencia: la base no respondió; se usa el contador en memoria")
            db.rollback()
    return _memoria_espera(clave, maximo, ventana)


def anotar_intento(request: Request, nombre: str, db: Session | None = None, ventana: int | None = None) -> None:
    """Suma un intento a la cuenta (en login se llama solo cuando el intento falla)."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    _, ventana = _parametros(None, ventana)
    clave = _clave(request, nombre)
    if _usar_base(db):
        try:
            _base_anotar(db, clave, ventana)
            return
        except Exception:
            log.exception("Límite de frecuencia: no se pudo guardar el intento; se usa el contador en memoria")
            db.rollback()
    _memoria_anotar(clave)


def verificar(request: Request, nombre: str, maximo: int | None = None, ventana: int | None = None,
              db: Session | None = None) -> None:
    """Rechaza con 429 (y lo audita) si ya se alcanzó el máximo de intentos en la ventana."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    maximo, ventana = _parametros(maximo, ventana)
    espera = _espera(db, _clave(request, nombre), maximo, ventana)
    if espera <= 0:
        return
    if db is not None:
        from services import auditoria_service as audit  # importación diferida: evita un ciclo

        audit.registrar(db, request, None, "seguridad", "limite_frecuencia", resultado="fallo",
                        detalle=f"{nombre}: {maximo} intentos en {ventana} s desde {ip_cliente(request)}")
    raise HTTPException(
        status_code=429,
        detail=f"Demasiados intentos desde tu conexión. Esperá {espera} segundos y volvé a intentar.",
        headers={"Retry-After": str(espera)},
    )


def limitar(request: Request, nombre: str, maximo: int | None = None, ventana: int | None = None,
            db: Session | None = None) -> None:
    """Verifica y, si pasa, cuenta el intento (registro, recuperación: toda solicitud cuenta)."""
    verificar(request, nombre, maximo, ventana, db)
    anotar_intento(request, nombre, db, ventana)


def dependencia(nombre: str, maximo: int | None = None, ventana: int | None = None, solo_verificar: bool = False):
    """Dependencia de FastAPI. Con `solo_verificar=True` no suma el intento: el endpoint decide
    cuándo contarlo con `anotar_intento` (en el login, solo los fallidos)."""
    def _dep(request: Request, db: Session = Depends(get_db)):
        if solo_verificar:
            verificar(request, nombre, maximo, ventana, db)
        else:
            limitar(request, nombre, maximo, ventana, db)

    return _dep
