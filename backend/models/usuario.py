from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    rol = Column(String, default="dermatologo")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
