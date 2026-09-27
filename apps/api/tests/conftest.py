"""Real PostgreSQL fixtures, isolated from the development database."""

import os
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker


def checked_test_urls() -> tuple[URL, URL]:
    development = os.environ.get("DATABASE_URL")
    test = os.environ.get("TEST_DATABASE_URL")
    if not development or not test:
        raise RuntimeError("DATABASE_URL and TEST_DATABASE_URL are required for PostgreSQL tests")
    development_url, test_url = make_url(development), make_url(test)
    if development_url.query or test_url.query:
        raise RuntimeError("PostgreSQL test URLs must not contain query parameters")
    if (
        development_url.drivername != "postgresql+psycopg"
        or test_url.drivername != "postgresql+psycopg"
    ):
        raise RuntimeError("PostgreSQL tests require the postgresql+psycopg dialect")
    if development_url.database != "investment_tracker":
        raise RuntimeError("DATABASE_URL must target the local investment_tracker database")
    if test_url.database != "investment_tracker_test":
        raise RuntimeError("TEST_DATABASE_URL must target only investment_tracker_test")
    if development_url.database == test_url.database:
        raise RuntimeError("Test and development databases must differ")
    if (development_url.host, development_url.port, development_url.username) != (
        test_url.host,
        test_url.port,
        test_url.username,
    ):
        raise RuntimeError("Test and development URLs must use the same local PostgreSQL server")
    if test_url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Test bootstrap is restricted to local PostgreSQL")
    validated_test_url = URL.create(
        drivername="postgresql+psycopg",
        username=test_url.username,
        password=test_url.password,
        host=test_url.host,
        port=test_url.port,
        database="investment_tracker_test",
    )
    return development_url, validated_test_url


@pytest.fixture(scope="session")
def test_session_factory() -> Iterator[sessionmaker[Session]]:
    _, test_url = checked_test_urls()
    with psycopg.connect(
        host=test_url.host,
        port=test_url.port or 5432,
        user=test_url.username,
        password=test_url.password,
        dbname="postgres",
        autocommit=True,
    ) as maintenance:
        with maintenance.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                ("investment_tracker_test",),
            )
            cursor.execute("DROP DATABASE IF EXISTS investment_tracker_test")
            cursor.execute("CREATE DATABASE investment_tracker_test")

    old_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if old_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_database_url

    engine = create_engine(test_url)
    try:
        yield sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def clean_db(test_session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    engine = test_session_factory.kw["bind"]
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE transactions, investment_accounts, instruments, portfolios "
                "RESTART IDENTITY"
            )
        )
    return test_session_factory
