"""Operator safety/metadata tests without any cloud or database access."""

import subprocess
from pathlib import Path

import pytest

from operator_tools import backup as tool


def manifest():
    return {
        "backup_format_version": 1,
        "created_at_utc": "2026-10-07T00:00:00+00:00",
        "source_environment": "production",
        "source_alembic_revision": tool.HEAD,
        "source_postgresql_version": "18.6",
        "pg_dump_version": "pg_dump (PostgreSQL) 18.6",
        "application_git_revision": "a" * 40,
        "row_counts": dict.fromkeys(tool.tables(tool.HEAD), 0),
    }


@pytest.mark.parametrize("target", ["local", "staging"])
def test_production_to_nonproduction_forbidden(monkeypatch, tmp_path, target):
    monkeypatch.setattr(tool, "unpack", lambda *_: manifest())
    monkeypatch.setattr(tool, "connection", lambda _: pytest.fail("must reject before connection"))
    with pytest.raises(tool.BackupError, match="crossover"):
        tool.restore(tmp_path / "production.tar", target)


def test_nonproduction_to_production_forbidden(monkeypatch, tmp_path):
    value = manifest()
    value["source_environment"] = "staging"
    monkeypatch.setattr(tool, "unpack", lambda *_: value)
    with pytest.raises(tool.BackupError, match="crossover"):
        tool.restore(tmp_path / "staging.tar", "production")


@pytest.mark.parametrize("ack,writes", [(False, False), (True, False), (False, True)])
def test_production_restore_requires_both_acknowledgments(monkeypatch, tmp_path, ack, writes):
    monkeypatch.setattr(tool, "unpack", lambda *_: manifest())
    with pytest.raises(tool.BackupError, match="acknowledgments"):
        tool.restore(
            tmp_path / "production.tar",
            "production",
            production_recovery=ack,
            writes_stopped=writes,
        )


def test_production_backup_requires_encrypted_storage(tmp_path):
    with pytest.raises(tool.BackupError, match="encrypted"):
        tool.backup(tmp_path, "production")


@pytest.mark.parametrize(
    "field,value",
    [
        ("created_at_utc", "not a timestamp"),
        ("created_at_utc", "2026-01-01T00:00:00"),
        ("source_environment", "preview"),
        ("application_git_revision", "not-sha"),
        ("source_postgresql_version", "password"),
        ("pg_dump_version", "invalid"),
        ("row_counts", {}),
        ("backup_format_version", True),
    ],
)
def test_invalid_manifest(field, value):
    data = manifest()
    data[field] = value
    with pytest.raises(tool.BackupError):
        tool.manifest_check(data)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "postgresql://user:secret@host/db",
        "postgresql://user:secret@ep-test-pooler.neon.tech/db?sslmode=require",
    ],
)
def test_unsafe_connection(monkeypatch, url):
    monkeypatch.setenv("BACKUP_DATABASE_URL", url)
    with pytest.raises(tool.BackupError) as error:
        tool.connection("BACKUP_DATABASE_URL")
    assert "secret" not in str(error.value)


def test_connection_credentials_only_in_environment(monkeypatch):
    monkeypatch.setenv("BACKUP_DATABASE_URL", "postgresql://user:secret@127.0.0.1/db")
    monkeypatch.setenv("PGSERVICE", "unexpected")
    _, environment = tool.connection("BACKUP_DATABASE_URL")
    assert environment["PGPASSWORD"] == "secret"
    assert "PGSERVICE" not in environment


def test_native_failure_does_not_leak_credentials(monkeypatch):
    def failure(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "pg_dump", stderr="secret password")

    monkeypatch.setattr(tool.subprocess, "run", failure)
    with pytest.raises(tool.BackupError) as error:
        tool.pg("pg_dump", [])
    assert "secret" not in str(error.value)


def test_incomplete_artifact_rejected(tmp_path):
    with pytest.raises(tool.BackupError, match="Incomplete"):
        tool.validate(Path(tmp_path / "bundle.incomplete"))


def test_environment_endpoint_bindings(monkeypatch):
    monkeypatch.setenv("STAGING_DATABASE_HOST", "staging.example")
    monkeypatch.setenv("PRODUCTION_DATABASE_HOST", "production.example")
    monkeypatch.setenv("PRODUCTION_RECOVERY_HOST", "recovery.example")
    for environment, host in [
        ("staging", "production.example"),
        ("production", "staging.example"),
        ("local", "production.example"),
    ]:
        with pytest.raises(tool.BackupError):
            tool.environment_guard(f"postgresql://user@{host}/db", environment)
    tool.environment_guard("postgresql://user@staging.example/db", "staging")
    tool.environment_guard("postgresql://user@recovery.example/db", "production", recovery=True)
    monkeypatch.setenv("PRODUCTION_RECOVERY_HOST", "staging.example")
    with pytest.raises(tool.BackupError):
        tool.environment_guard("postgresql://user@staging.example/db", "production", recovery=True)


def test_distribution_client_version():
    value = manifest()
    value["pg_dump_version"] = "pg_dump (PostgreSQL) 18.6 (Ubuntu 18.6-1.pgdg24.04+1)"
    assert tool.manifest_check(value) == value


def test_database_name_cannot_override_verified_endpoint(monkeypatch):
    monkeypatch.setenv("RESTORE_DATABASE_URL", "host=127.0.0.1 dbname='host=other dbname=wrong'")
    with pytest.raises(tool.BackupError, match="database name"):
        tool.connection("RESTORE_DATABASE_URL")


@pytest.mark.parametrize("directory", [tool.ROOT.parents[1], tool.ROOT.parents[1] / "backups"])
def test_backup_cannot_enter_deployment_sources(monkeypatch, directory):
    monkeypatch.setenv("BACKUP_DATABASE_URL", "postgresql://user@127.0.0.1/synthetic")
    with pytest.raises(tool.BackupError, match="outside the checkout"):
        tool.backup(directory, "local")


def test_interrupted_directory_cannot_be_restored(tmp_path):
    with pytest.raises(tool.BackupError, match="Incomplete"):
        tool.restore(tmp_path / ".incomplete-abandoned" / "bundle.tar", "local")
