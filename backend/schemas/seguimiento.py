from datetime import datetime

from pydantic import BaseModel


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
