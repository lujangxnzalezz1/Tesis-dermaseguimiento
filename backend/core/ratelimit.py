"""Limitador de frecuencia simple en memoria, por IP (punto 0).
Suficiente para un solo proceso; con varios workers debe reemplazarse por Redis."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from core.config import settings

_eventos: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def reiniciar():
    with _lock:
        _eventos.clear()


def limitar(request: Request, nombre: str, maximo: int | None = None, ventana: int | None = None):
    if not settings.RATE_LIMIT_ENABLED:
        return
    maximo = maximo or settings.RATE_LIMIT_AUTH_MAX
    ventana = ventana or settings.RATE_LIMIT_AUTH_WINDOW_SECONDS
    ip = request.client.host if request.client else "desconocida"
    clave = f"{nombre}:{ip}"
    ahora_ = time.monotonic()
    with _lock:
        cola = _eventos[clave]
        while cola and cola[0] <= ahora_ - ventana:
            cola.popleft()
        if len(cola) >= maximo:
            espera = int(ventana - (ahora_ - cola[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Demasiados intentos desde tu conexión. Esperá {espera} segundos y volvé a intentar.",
                headers={"Retry-After": str(espera)},
            )
        cola.append(ahora_)


def dependencia(nombre: str, maximo: int | None = None, ventana: int | None = None):
    def _dep(request: Request):
        limitar(request, nombre, maximo, ventana)

    return _dep
