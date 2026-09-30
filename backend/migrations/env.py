from alembic import context
from sqlalchemy import create_engine

from core.config import settings
from core.database import Base
import models  # noqa: F401 - registra todas las tablas en Base.metadata

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
