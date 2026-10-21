from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func

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
    # Borrado lógico: la plantilla deja de listarse pero queda constancia de que existió
    eliminada_en = Column(DateTime, nullable=True)


# Un mismo título (sin distinguir mayúsculas) no se repite entre las plantillas VIGENTES de cada profesional.
# Índice único parcial: las borradas no cuentan, así se puede volver a crear una con el mismo título.
Index(
    "uq_plantilla_usuario_titulo",
    PlantillaIndicacion.usuario_id, func.lower(PlantillaIndicacion.titulo),
    unique=True,
    postgresql_where=PlantillaIndicacion.eliminada_en.is_(None),
    sqlite_where=PlantillaIndicacion.eliminada_en.is_(None),
)
