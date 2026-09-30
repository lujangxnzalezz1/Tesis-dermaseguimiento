from datetime import datetime, timezone


def ahora() -> datetime:
    """Hora actual del SERVIDOR en UTC (sin tzinfo, como se guarda en la base).
    Se usa siempre el reloj del servidor para garantizar la integridad de los registros."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
