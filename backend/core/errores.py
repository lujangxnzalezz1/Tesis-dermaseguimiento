"""Manejo global de errores (puntos 17, 18 y RNF-18).

Ninguna respuesta expone SQL, rutas internas, trazas ni claves: el detalle técnico
va solo a los logs del servidor.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("errores")

_MENSAJES = {
    "missing": "es obligatorio",
    "string_too_short": "es demasiado corto",
    "string_too_long": "es demasiado largo",
    "int_parsing": "debe ser un número entero",
    "float_parsing": "debe ser un número",
    "bool_parsing": "debe ser verdadero o falso",
    "date_parsing": "debe ser una fecha válida (AAAA-MM-DD)",
    "date_from_datetime_parsing": "debe ser una fecha válida (AAAA-MM-DD)",
    "greater_than": "es menor al valor permitido",
    "greater_than_equal": "es menor al valor permitido",
    "less_than": "supera el valor permitido",
    "less_than_equal": "supera el valor permitido",
    "json_invalid": "el cuerpo de la solicitud no es un JSON válido",
    "literal_error": "tiene un valor no permitido",
    "enum": "tiene un valor no permitido",
    "string_pattern_mismatch": "tiene un formato incorrecto",
    "missing_argument": "es obligatorio",
}


def _mensaje(err: dict) -> str:
    tipo = err.get("type", "")
    if tipo == "value_error":
        msg = str(err.get("msg", ""))
        return msg.removeprefix("Value error, ")
    return _MENSAJES.get(tipo, "no es válido")


def _campo(err: dict) -> str:
    partes = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path", "form")]
    return ".".join(partes) or "solicitud"


def instalar(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError):
        errores = [{"campo": _campo(e), "mensaje": _mensaje(e)} for e in exc.errors()]
        texto = "; ".join(
            e["mensaje"] if e["mensaje"].startswith(("La ", "El ", "Las ", "Los ", "Tenés ")) else f"El campo «{e['campo']}» {e['mensaje']}"
            for e in errores
        )
        return JSONResponse(
            status_code=422,
            content={"detail": f"Revisá los datos ingresados: {texto}.", "errores": errores},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not isinstance(exc.detail, str):
            detalle = "No encontramos lo que buscás."
        elif isinstance(exc.detail, str):
            detalle = exc.detail
        else:
            detalle = "No se pudo completar la operación."
        if detalle == "Not authenticated":
            detalle = "Necesitás iniciar sesión para continuar."
        if exc.status_code == 404 and detalle == "Not Found":
            detalle = "No encontramos lo que buscás."
        if exc.status_code == 405:
            detalle = "Esta operación no está permitida."
        return JSONResponse(status_code=exc.status_code, content={"detail": detalle}, headers=exc.headers)

    @app.exception_handler(IntegrityError)
    async def _integridad(request: Request, exc: IntegrityError):
        log.warning("Violación de integridad: %s", exc.orig)
        return JSONResponse(
            status_code=409,
            content={"detail": "Ese registro ya existe o entra en conflicto con otro. Revisá los datos e intentá de nuevo."},
        )

    @app.exception_handler(OperationalError)
    async def _conexion(request: Request, exc: OperationalError):
        log.error("Base de datos no disponible: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "El servicio no está disponible en este momento. Intentá de nuevo en unos minutos."},
        )

    @app.exception_handler(SQLAlchemyError)
    async def _bd(request: Request, exc: SQLAlchemyError):
        log.exception("Error de base de datos")
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocurrió un problema al guardar la información. No se realizaron cambios; intentá de nuevo."},
        )

    @app.exception_handler(Exception)
    async def _general(request: Request, exc: Exception):
        log.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocurrió un error inesperado. Intentá de nuevo; si persiste, contactá al soporte."},
        )
