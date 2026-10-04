import importlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool, QueuePool

from app import bootstrap
from app.config import database_url, migration_database_url


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch):
    for key in ("VERCEL", "DATABASE_POOL_MODE", "MIGRATION_DATABASE_URL", "CLOUD_BOOTSTRAP_ONLY"):
        monkeypatch.delenv(key, raising=False)
    bootstrap.session_factory.cache_clear()
    yield
    bootstrap.session_factory.cache_clear()


def test_bootstrap_has_no_database_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUD_BOOTSTRAP_ONLY", "1")
    monkeypatch.setenv("DATABASE_URL", "not-a-usable-production-url")
    with patch("sqlalchemy.create_engine", side_effect=AssertionError("DB forbidden")):
        from app import vercel

        importlib.reload(vercel)
        with TestClient(vercel.app) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert client.get("/portfolios").status_code == 404
            assert client.post("/portfolios", json={"name": "forbidden"}).status_code == 404
    monkeypatch.delenv("CLOUD_BOOTSTRAP_ONLY")
    importlib.reload(vercel)


def test_normal_cloud_health_does_not_create_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with patch("app.bootstrap.create_engine", side_effect=AssertionError("DB forbidden")):
        from app.vercel import create_app

        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200


def test_cloud_pool_and_tls_preserve_normal_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://owner:fake@ep-example-pooler.eu-central-1.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require",
    )
    factory = bootstrap.session_factory()
    engine = factory.kw["bind"]
    assert isinstance(engine.pool, NullPool)
    assert engine.url.drivername == "postgresql+psycopg"
    assert dict(engine.url.query) == {"sslmode": "require", "channel_binding": "require"}
    assert "prepare_threshold" not in engine.dialect.create_connect_args(engine.url)[1]
    engine.dispose()


def test_local_pool_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://fake:fake@localhost/local")
    engine = bootstrap.session_factory().kw["bind"]
    assert isinstance(engine.pool, QueuePool)
    assert migration_database_url() == database_url()
    engine.dispose()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://fake:fake@localhost/local?sslmode=require",
        "postgresql://fake:fake@ep-example.neon.tech/neondb?sslmode=require",
        "postgresql://fake:fake@ep-example-pooler.neon.tech/neondb?sslmode=disable",
    ],
)
def test_cloud_rejects_unsafe_connections(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError):
        database_url()


def test_cloud_migration_requires_operator_direct_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_POOL_MODE", "serverless")
    with pytest.raises(RuntimeError, match="MIGRATION_DATABASE_URL"):
        migration_database_url()
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL",
        "postgresql://fake:fake@ep-example.neon.tech/neondb?sslmode=require",
    )
    assert migration_database_url().host == "ep-example.neon.tech"
