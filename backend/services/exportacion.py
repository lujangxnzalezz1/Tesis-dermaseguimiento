"""Exportación a CSV verificable (punto 23): encabezados, fechas ISO, separador decimal
elegible, acentos (UTF-8 con BOM para Excel), totales, filtros aplicados, nombre con fecha."""
import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional, Sequence

from fastapi import Response

from core.tiempo import ahora


def _fmt(valor, decimal: str):
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valor, (float, Decimal)):
        texto = f"{valor:.2f}" if isinstance(valor, Decimal) else f"{valor:.4f}".rstrip("0").rstrip(".")
        return texto.replace(".", ",") if decimal == "coma" else texto
    return str(valor)


def _neutralizar(texto: str) -> str:
    # Evita inyección de fórmulas al abrir el CSV en Excel/Calc
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") and not texto.replace(",", "").replace(".", "").replace("-", "").isdigit() else texto


def respuesta_csv(
    titulo: str, encabezados: Sequence[str], filas: Iterable[Sequence], *, filtros: dict, decimal: str = "coma",
    totales: Optional[dict[str, object]] = None, prefijo_archivo: str = "reporte",
) -> Response:
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    generado = ahora()
    w.writerow(["Reporte", titulo])
    w.writerow(["Generado (hora del servidor, UTC)", generado.strftime("%Y-%m-%d %H:%M:%S")])
    w.writerow(["Filtros aplicados", "; ".join(f"{k}={v}" for k, v in filtros.items() if v not in (None, "")) or "ninguno"])
    w.writerow([])
    w.writerow(encabezados)
    n = 0
    for fila in filas:
        w.writerow([_neutralizar(c) if isinstance(c, str) else _fmt(c, decimal) for c in fila])
        n += 1
    w.writerow([])
    w.writerow(["Total de registros", n])
    for k, v in (totales or {}).items():
        w.writerow([k, _fmt(v, decimal) if not isinstance(v, str) else v])
    cuerpo = ("﻿" + salida.getvalue()).encode("utf-8")
    nombre = f"{prefijo_archivo}_{generado.strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=cuerpo, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
