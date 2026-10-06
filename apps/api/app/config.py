"""Environment-backed configuration needed by the running API."""

import os

from sqlalchemy.engine import URL, make_url


def serverless_database() -> bool:
    mode = os.environ.get(
        "DATABASE_POOL_MODE", "serverless" if os.environ.get("VERCEL") else "local"
    )
    if mode not in {"local", "serverless"}:
        raise RuntimeError("DATABASE_POOL_MODE must be local or serverless")
    if os.environ.get("VERCEL") and mode != "serverless":
        raise RuntimeError("Vercel requires serverless database pooling")
    return mode == "serverless"


def _postgres_url(value: str, *, cloud: bool, pooled: bool) -> URL:
    url = make_url(value)
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise RuntimeError("PostgreSQL with Psycopg is required")
    url = url.set(drivername="postgresql+psycopg")
    if cloud:
        if not url.host or not url.host.endswith(".neon.tech"):
            raise RuntimeError("Cloud database must use Neon")
        if ("-pooler" in url.host) != pooled:
            raise RuntimeError(
                "Cloud runtime requires pooled; migrations require direct connections"
            )
        if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise RuntimeError("Cloud PostgreSQL requires TLS")
    return url


def database_url() -> URL:
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required for persistence requests")
    return _postgres_url(value, cloud=serverless_database(), pooled=True)


def migration_database_url() -> URL:
    value = os.environ.get("MIGRATION_DATABASE_URL")
    cloud = serverless_database()
    if value:
        return _postgres_url(value, cloud=cloud, pooled=False)
    if cloud:
        raise RuntimeError("MIGRATION_DATABASE_URL is required for explicit cloud migrations")
    return database_url()
