from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from core.database import Base
from core.tiempo import ahora


class PlantillaIndicacion(Base):
    """Indicaciones que la profesional escribe una vez y reutiliza en sus informes (las redacta ella, no la app)."""

    __tablename__ = "plantillas_indicacion"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    titulo = Column(String(60), nullable=False)
    texto = Column(Text, nullable=False)
    creada_en = Column(DateTime, nullable=False, default=ahora)
