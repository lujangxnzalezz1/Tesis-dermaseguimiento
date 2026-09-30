from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import obtener_usuario_actual
from models.seguimiento import Seguimiento
from models.usuario import Usuario
from routers.pacientes import obtener_paciente_propio
from services import auditoria_service as audit
from services.exportacion import respuesta_csv
from services.suscripcion_service import exigir_acceso_avanzado

router = APIRouter(prefix="/pacientes", tags=["Reportes"])


def _consulta(db, paciente_id, desde, hasta):
    q = db.query(Seguimiento).filter(Seguimiento.paciente_id == paciente_id)
    if desde:
        q = q.filter(Seguimiento.fecha >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.filter(Seguimiento.fecha < datetime.combine(hasta, datetime.min.time()) + timedelta(days=1))
    return q.order_by(Seguimiento.fecha.asc()).all()


@router.get("/{paciente_id}/reporte")
def reporte_evolucion(
    paciente_id: int, desde: Optional[date] = None, hasta: Optional[date] = None,
    db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual),
):
    """RF-17: serie de métricas por consulta para graficar la evolución del paciente."""
    exigir_acceso_avanzado(db, usuario)
    pac = obtener_paciente_propio(db, usuario, paciente_id, incluir_inactivos=True)
    filas = _consulta(db, pac.id, desde, hasta)
    serie = [
        {"seguimiento_id": s.id, "fecha": s.fecha.isoformat(), "delta_e_promedio": round(s.delta_e_promedio, 3),
         "l": round(s.l_nueva, 3), "a": round(s.a_nueva, 3), "b": round(s.b_nueva, 3),
         "ojeras_contraste": s.ojeras_contraste_nueva, "lesiones": s.lesiones_nueva, "lesiones_nuevas": s.lesiones_nuevas}
        for s in filas
    ]
    return {
        "paciente": {"id": pac.id, "nombre": pac.nombre, "apellido": pac.apellido, "cedula": pac.cedula},
        "filtros": {"desde": desde, "hasta": hasta},
        "total_consultas": len(serie),
        "delta_e_promedio_general": round(sum(x["delta_e_promedio"] for x in serie) / len(serie), 3) if serie else None,
        "serie": serie,
    }


@router.get("/{paciente_id}/reporte.csv")
def reporte_evolucion_csv(
    paciente_id: int, request: Request, desde: Optional[date] = None, hasta: Optional[date] = None,
    decimal: str = Query("coma", pattern="^(coma|punto)$"),
    db: Session = Depends(get_db), usuario: Usuario = Depends(obtener_usuario_actual),
):
    exigir_acceso_avanzado(db, usuario)
    pac = obtener_paciente_propio(db, usuario, paciente_id, incluir_inactivos=True)
    filas = _consulta(db, pac.id, desde, hasta)
    promedio = sum(s.delta_e_promedio for s in filas) / len(filas) if filas else None
    audit.registrar(db, request, usuario, "reportes", "exportar_csv", entidad="paciente", entidad_id=pac.id)
    return respuesta_csv(
        f"Evolución colorimétrica - {pac.nombre} {pac.apellido} (CI {pac.cedula})",
        ["Fecha", "Delta E promedio", "L* (nueva)", "a* (nueva)", "b* (nueva)", "Contraste ojeras (L*)", "Lesiones", "Lesiones nuevas",
         "SSIM sin alinear", "SSIM alineada", "Tiempo de procesamiento (ms)"],
        [(s.fecha, s.delta_e_promedio, s.l_nueva, s.a_nueva, s.b_nueva, s.ojeras_contraste_nueva, s.lesiones_nueva, s.lesiones_nuevas,
          s.ssim_antes, s.ssim_despues, s.tiempo_procesamiento_ms) for s in filas],
        filtros={"desde": desde, "hasta": hasta, "separador_decimal": decimal},
        totales={"Delta E promedio general": promedio} if promedio is not None else None,
        decimal=decimal, prefijo_archivo=f"evolucion_ci{pac.cedula}",
    )
