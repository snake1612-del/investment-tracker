"""Run reviewed schema migrations against DATABASE_URL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import database_url
from app.infrastructure.db import models  # noqa: F401 - populate Base.metadata
from app.infrastructure.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations_online()
