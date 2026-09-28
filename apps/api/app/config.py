"""Environment-backed configuration needed by the running API."""

import os


def database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required for persistence requests")
    return value
