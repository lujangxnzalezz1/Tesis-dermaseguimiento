from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DateTime

from core.database import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    fecha_nacimiento = Column(Date, nullable=True)
    sexo = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    antecedentes_medicos = Column(String, nullable=True)
    observaciones = Column(String, nullable=True)
    dermatologo_id = Column(Integer, nullable=False)  # quién lo registró
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
