"""Valoración clínica que registra la PROFESIONAL (la app no la estima a partir de las fotos).

- IGA (Investigator's Global Assessment) para acné: grado 0 a 4.
- mMASI (Modified Melasma Area and Severity Index; Pandya et al., 2011): por región, área (0-6) y
  oscuridad (0-4); total = 0,3·A·D(frente) + 0,3·A·D(malar der.) + 0,3·A·D(malar izq.) + 0,1·A·D(mentón),
  de 0 a 24.
- Mediciones con equipo externo (corneómetro, pHmetro, cutómetro): se guardan tal como las mide el
  equipo, con el nombre del equipo para que las unidades sean comparables entre consultas.
"""
from typing import Optional

from pydantic import BaseModel, Field

IGA_GRADOS = {
    0: "Sin lesiones (limpio)",
    1: "Casi limpio",
    2: "Leve",
    3: "Moderado",
    4: "Severo",
}
MASI_PESOS = {"frente": 0.3, "malar_derecha": 0.3, "malar_izquierda": 0.3, "menton": 0.1}
MASI_NOMBRES = {"frente": "Frente", "malar_derecha": "Mejilla derecha", "malar_izquierda": "Mejilla izquierda", "menton": "Mentón"}


class RegionMasi(BaseModel):
    area: int = Field(..., ge=0, le=6)
    oscuridad: int = Field(..., ge=0, le=4)


class Masi(BaseModel):
    frente: RegionMasi
    malar_derecha: RegionMasi
    malar_izquierda: RegionMasi
    menton: RegionMasi


class ValoracionClinica(BaseModel):
    iga: Optional[int] = Field(None, ge=0, le=4)
    masi: Optional[Masi] = None
    humedad: Optional[float] = Field(None, ge=0, le=150, description="Hidratación (unidades del corneómetro)")
    ph: Optional[float] = Field(None, ge=3, le=9)
    firmeza: Optional[float] = Field(None, ge=0, le=100, description="Firmeza/elasticidad (escala del equipo)")
    equipo: Optional[str] = Field(None, max_length=120)


def puntaje_mmasi(masi: Optional[dict]) -> Optional[float]:
    if not masi:
        return None
    return round(sum(MASI_PESOS[r] * masi[r]["area"] * masi[r]["oscuridad"] for r in MASI_PESOS), 1)


def normalizar(v: ValoracionClinica) -> Optional[dict]:
    """Lo que se guarda: lo cargado más el mMASI calculado y la descripción del IGA. None si no se cargó nada."""
    d = v.model_dump(exclude_none=True)
    if v.equipo is not None:
        d["equipo"] = v.equipo.strip() or None
        if d["equipo"] is None:
            d.pop("equipo")
    if not {k for k in d if k != "equipo"}:
        return None
    if "masi" in d:
        d["mmasi"] = puntaje_mmasi(d["masi"])
    if "iga" in d:
        d["iga_texto"] = IGA_GRADOS[d["iga"]]
    return d
