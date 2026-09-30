from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base
from core.tiempo import ahora


class Seguimiento(Base):
    __tablename__ = "seguimientos"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha = Column(DateTime, default=ahora, index=True)

    # Las rutas son claves opacas (UUID): no contienen datos de identificación (RNF-02).
    ruta_imagen_referencia = Column(String, nullable=False)
    ruta_imagen_nueva = Column(String, nullable=False)
    ruta_imagen_alineada = Column(String, nullable=False)

    landmarks_referencia = Column(Integer, nullable=False)
    landmarks_nueva = Column(Integer, nullable=False)

    ruta_mapa_calor = Column(String, nullable=False)
    delta_e_promedio = Column(Float, nullable=False)
    l_referencia = Column(Float, nullable=False)
    a_referencia = Column(Float, nullable=False)
    b_referencia = Column(Float, nullable=False)
    l_nueva = Column(Float, nullable=False)
    a_nueva = Column(Float, nullable=False)
    b_nueva = Column(Float, nullable=False)

    # RNF-06: tiempo de procesamiento medido en el servidor
    tiempo_procesamiento_ms = Column(Integer, nullable=True)

    paciente = relationship("Paciente")
    usuario = relationship("Usuario")
