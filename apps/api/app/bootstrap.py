"""Composition root connecting environment, SQLAlchemy, and application contracts."""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.application.contracts import UnitOfWork
from app.application.use_cases import UowFactory
from app.config import database_url
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


@lru_cache
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(database_url())
    return sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


def get_uow_factory() -> UowFactory:
    factory = session_factory()

    def make_uow() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(factory)

    return make_uow
