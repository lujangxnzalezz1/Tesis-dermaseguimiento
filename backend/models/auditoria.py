from sqlalchemy import Column, DateTime, Integer, String, Text, event

from core.database import Base
from core.tiempo import ahora


class Auditoria(Base):
    """Bitácora de auditoría. Solo se inserta: nunca se modifica ni se borra
    (ver el disparador de PostgreSQL en la migración y los eventos de abajo)."""

    __tablename__ = "auditoria"

    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, nullable=False, default=ahora, index=True)  # reloj del servidor
    usuario_id = Column(Integer, nullable=True, index=True)
    usuario_email = Column(String, nullable=True)
    ip = Column(String, nullable=True)
    modulo = Column(String, nullable=False, index=True)
    accion = Column(String, nullable=False, index=True)
    entidad = Column(String, nullable=True)
    entidad_id = Column(String, nullable=True)
    datos_antes = Column(Text, nullable=True)
    datos_despues = Column(Text, nullable=True)
    resultado = Column(String, nullable=False, default="exito")  # exito | fallo
    detalle = Column(String, nullable=True)


@event.listens_for(Auditoria, "before_update")
@event.listens_for(Auditoria, "before_delete")
def _auditoria_inmutable(mapper, connection, target):
    raise PermissionError("Los registros de auditoría no pueden modificarse ni eliminarse.")
