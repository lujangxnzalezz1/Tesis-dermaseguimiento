from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint,
)

from core.database import Base
from core.tiempo import ahora


class Paciente(Base):
    __tablename__ = "pacientes"
    # La cédula es única dentro de la cartera de cada dermatólogo (consultorios independientes).
    __table_args__ = (UniqueConstraint("dermatologo_id", "cedula", name="uq_paciente_dermatologo_cedula"),)

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column(String, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    fecha_nacimiento = Column(Date, nullable=True)
    sexo = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    antecedentes_medicos = Column(String, nullable=True)
    observaciones = Column(String, nullable=True)
    dermatologo_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)  # quién lo registró
    fecha_creacion = Column(DateTime, default=ahora)

    # Borrado lógico (punto 20) y control de concurrencia (punto 30)
    activo = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    eliminado_en = Column(DateTime, nullable=True)
    eliminado_por = Column(Integer, nullable=True)
    motivo_eliminacion = Column(String, nullable=True)
    fecha_modificacion = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")


class ConsentimientoPaciente(Base):
    """Evidencia del consentimiento informado del paciente (RNF-24)."""

    __tablename__ = "consentimientos"

    id = Column(Integer, primary_key=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    registrado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)
    version_politica = Column(String, nullable=False)
    finalidad = Column(String, nullable=False)
    revocado_en = Column(DateTime, nullable=True, index=True)  # se filtra por «vigente» (revocado_en IS NULL)
    motivo_revocacion = Column(String, nullable=True)
