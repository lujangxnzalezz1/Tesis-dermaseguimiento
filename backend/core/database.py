from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from core.config import settings

_argumentos = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # Solo para las pruebas automáticas (base en memoria compartida).
    _argumentos = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, **_argumentos)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
