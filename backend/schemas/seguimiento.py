from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SeguimientoRespuesta(BaseModel):
    id: int
    paciente_id: int
    fecha: datetime
    landmarks_referencia: int
    landmarks_nueva: int
    url_imagen_referencia: str
    url_imagen_nueva: str
    url_imagen_alineada: str

    # Análisis colorimétrico en espacio CIE L*a*b*
    delta_e_promedio: float
    l_referencia: float
    a_referencia: float
    b_referencia: float
    l_nueva: float
    a_nueva: float
    b_nueva: float
    url_mapa_calor: str
    tiempo_procesamiento_ms: Optional[int] = None
    ssim_antes: Optional[float] = None
    ssim_despues: Optional[float] = None
    lesiones_referencia: Optional[int] = None
    lesiones_nueva: Optional[int] = None
    lesiones_nuevas: Optional[int] = None
    lesiones_persistentes: Optional[int] = None
    lesiones_resueltas: Optional[int] = None
    url_imagen_lesiones: Optional[str] = None
    ojeras_contraste_referencia: Optional[float] = None
    ojeras_contraste_nueva: Optional[float] = None
    ojeras_detalle: Optional[dict] = None
    url_imagen_periorbital: Optional[str] = None
    manchas_pct_referencia: Optional[float] = None
    manchas_pct_nueva: Optional[float] = None
    manchas_detalle: Optional[dict] = None
    url_imagen_manchas: Optional[str] = None
    textura_referencia: Optional[dict] = None
    textura_nueva: Optional[dict] = None
    url_imagen_textura: Optional[str] = None
    recomendaciones: Optional[str] = None
    interpretacion: Optional[dict] = None


class Recomendaciones(BaseModel):
    texto: str = Field("", max_length=2000)
