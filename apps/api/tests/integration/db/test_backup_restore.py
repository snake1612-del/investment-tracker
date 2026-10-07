"""Real native PostgreSQL drill, always using disposable local synthetic databases."""

import json
import tarfile
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import LiteralString

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.models import (
    InstrumentModel,
    InvestmentAccountModel,
    MarketPriceObservationModel,
    PortfolioModel,
    TransactionModel,
)
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app
from operator_tools import backup as tool
from tests.conftest import checked_test_urls


def native(url):
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


@contextmanager
def disposable_database():
    _, url = checked_test_urls()
    name = "investment_tracker_recovery_" + uuid.uuid4().hex
    maintenance_url = native(url.set(database="postgres"))
    with psycopg.connect(maintenance_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield url.set(database=name)
    finally:
        with psycopg.connect(maintenance_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


def seed(factory):
    stamp = datetime(2020, 1, 2, 3, 4, 5, 123456, UTC)
    with factory() as session:
        p = PortfolioModel(
            name="Synthetic Recovery", base_currency="USD", created_at=stamp, updated_at=stamp
        )
        session.add(p)
        session.flush()
        accounts = [
            InvestmentAccountModel(
                portfolio_id=p.id, name=str(i), created_at=stamp, updated_at=stamp
            )
            for i in range(2)
        ]
        instruments = [
            InstrumentModel(name="Synthetic " + str(i), created_at=stamp, updated_at=stamp)
            for i in range(2)
        ]
        session.add_all([*accounts, *instruments])
        session.flush()
        buy = None
        for number, kind in enumerate(
            ["DEPOSIT", "WITHDRAWAL", "BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "TAX"]
        ):
            transaction = TransactionModel(
                account_id=accounts[0].id,
                type=kind,
                instrument_id=instruments[0].id if kind not in {"DEPOSIT", "WITHDRAWAL"} else None,
                quantity=Decimal("1.123456789012")
                if kind == "BUY"
                else (Decimal("3.987654321098") if kind == "SELL" else None),
                price=Decimal("9999.123456789012") if kind in {"BUY", "SELL"} else None,
                cash_amount=Decimal("123456789.12345678"),
                currency_code="USD",
                effective_date=date(2020, 1, number + 1),
                settlement_date=date(2020, 2, 1) if kind in {"BUY", "SELL"} else None,
                related_transaction_id=buy if kind in {"FEE", "TAX"} else None,
                note="Synthetic precise metadata",
                created_at=stamp,
                updated_at=stamp,
            )
            session.add(transaction)
            session.flush()
            if kind == "BUY":
                buy = transaction.id
        session.add(
            TransactionModel(
                account_id=accounts[1].id,
                type="DEPOSIT",
                cash_amount=Decimal("0.00000001"),
                currency_code="EUR",
                effective_date=date(2020, 1, 1),
                created_at=stamp,
                updated_at=stamp,
            )
        )
        for index, instrument in enumerate(instruments):
            session.add(
                MarketPriceObservationModel(
                    instrument_id=instrument.id,
                    price=Decimal("0") if index == 0 else Decimal("123.000000000001"),
                    currency_code="USD" if index == 0 else "EUR",
                    effective_date=date(2020, 1, 1),
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
        session.commit()


def facts(url):
    with psycopg.connect(native(url)) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchall()[0][0]
        rows = {
            name: connection.execute(
                sql.SQL("SELECT * FROM public.{} ORDER BY 1").format(sql.Identifier(name))
            ).fetchall()
            for name in tool.tables(revision)
        }
        constraints = connection.execute(
            "SELECT c.relname, con.conname, con.contype, "
            "CASE WHEN con.contype='c' THEN NULL ELSE pg_get_constraintdef(con.oid) END, "
            "con.convalidated "
            "FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
            "ORDER BY 1,2"
        ).fetchall()
        indexes = connection.execute(
            "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' "
            "ORDER BY 1,2"
        ).fetchall()
        sequence_names = connection.execute(
            "SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY 1"
        ).fetchall()
        sequences = {
            name: connection.execute(
                sql.SQL("SELECT last_value,is_called FROM public.{}").format(sql.Identifier(name))
            ).fetchone()
            for (name,) in sequence_names
        }
        return rows, constraints, indexes, sequences


@pytest.fixture
def artifact(clean_db, monkeypatch, tmp_path):
    seed(clean_db)
    _, url = checked_test_urls()
    monkeypatch.setenv("BACKUP_DATABASE_URL", native(url))
    return tool.backup(tmp_path / "backups", "local"), url


def test_exact_restore_drill(artifact, monkeypatch):
    archive, source = artifact
    expected = facts(source)
    assert tool.validate(archive)["source_alembic_revision"] == tool.HEAD
    with disposable_database() as target:
        monkeypatch.setenv("RESTORE_DATABASE_URL", native(target))
        tool.restore(archive, "local")
        actual = facts(target)
        assert set(actual[1]) == set(expected[1]), (
            set(actual[1]) - set(expected[1]),
            set(expected[1]) - set(actual[1]),
        )
        assert actual == expected
        engine = create_engine(target)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(factory)
        try:
            with TestClient(app) as client:
                assert client.get("/health").status_code == 200
                assert len(client.get("/accounts/1/transactions").json()) == 8
                for route in ["positions", "realised-pnl", "valuation", "money-summary"]:
                    assert (
                        client.get(f"/accounts/1/{route}?as_of_date=2020-01-08").status_code == 200
                    )
                assert (
                    client.get(
                        "/portfolios/1/performance?start_date=2020-01-02&end_date=2020-01-08"
                    ).status_code
                    == 200
                )
            with factory() as session:
                p = PortfolioModel(name="After restore", base_currency="USD")
                i = InstrumentModel(name="After restore")
                session.add_all([p, i])
                session.flush()
                a = InvestmentAccountModel(name="After restore", portfolio_id=p.id)
                session.add(a)
                session.flush()
                t = TransactionModel(
                    account_id=a.id,
                    type="DEPOSIT",
                    cash_amount=Decimal("1"),
                    currency_code="USD",
                    effective_date=date(2020, 1, 1),
                )
                m = MarketPriceObservationModel(
                    instrument_id=i.id,
                    price=Decimal("0"),
                    currency_code="USD",
                    effective_date=date(2020, 1, 1),
                )
                session.add_all([t, m])
                session.flush()
                assert (p.id, a.id, i.id, t.id, m.id) == (2, 3, 3, 10, 3)
                session.commit()
            with psycopg.connect(native(target)) as connection:
                invalid_statements: list[LiteralString] = [
                    "UPDATE transactions SET type='INVALID' WHERE id=1",
                    "UPDATE transactions SET cash_amount=-1 WHERE id=1",
                    "UPDATE transactions SET account_id=999999 WHERE id=1",
                    "UPDATE transactions SET related_transaction_id=id WHERE id=1",
                    "UPDATE market_price_observations SET price=-1 WHERE id=1",
                    "UPDATE market_price_observations SET instrument_id=999999 WHERE id=1",
                    "INSERT INTO market_price_observations (instrument_id,price,currency_code,"
                    "effective_date) VALUES (1,0,'USD','2020-01-01')",
                ]
                for statement in invalid_statements:
                    with pytest.raises(psycopg.IntegrityError), connection.transaction():
                        connection.execute(sql.SQL(statement))
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


def rewrite(archive, tmp_path, mutate):
    directory = tmp_path / "edited"
    directory.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(directory, filter="data")
    mutate(directory)
    (directory / "SHA256SUMS").write_text(
        "".join(
            f"{tool.sha(directory / name)}  {name}\n" for name in ["database.dump", "manifest.json"]
        ),
        "ascii",
    )
    edited = tmp_path / "edited.tar"
    with tarfile.open(edited, "w") as bundle:
        for name in sorted(tool.MEMBERS):
            bundle.add(directory / name, arcname=name)
    return edited


@pytest.mark.parametrize("change", ["manifest", "unknown", "newer", "version", "revision", "dump"])
def test_invalid_artifacts(artifact, tmp_path, change):
    archive, _ = artifact

    def mutate(directory):
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        if change == "manifest":
            manifest.pop("created_at_utc")
        elif change in {"unknown", "newer", "revision"}:
            manifest["source_alembic_revision"] = {
                "unknown": "unknown",
                "newer": "0003_future",
                "revision": "0001_initial_persistence",
            }[change]
        elif change == "version":
            manifest["backup_format_version"] = 2
        else:
            (directory / "database.dump").write_bytes(b"unreadable archive")
        path.write_text(json.dumps(manifest))

    edited = rewrite(archive, tmp_path, mutate)
    with pytest.raises(tool.BackupError):
        tool.validate(edited)


def test_checksum_mismatch(artifact, tmp_path):
    archive, _ = artifact
    edited = rewrite(archive, tmp_path, lambda d: None)
    directory = tmp_path / "edited"
    (directory / "database.dump").write_bytes(b"corrupt dump")
    with tarfile.open(edited, "w") as bundle:
        for name in sorted(tool.MEMBERS):
            bundle.add(directory / name, arcname=name)
    with pytest.raises(tool.BackupError, match="Checksum"):
        tool.validate(edited)


def test_nonempty_target_refused(artifact, monkeypatch):
    archive, source = artifact
    expected = facts(source)
    monkeypatch.setenv("RESTORE_DATABASE_URL", native(source))
    with pytest.raises(tool.BackupError, match="non-empty"):
        tool.restore(archive, "local")
    assert facts(source) == expected


@pytest.mark.parametrize(
    ("create", "inspect"),
    [
        (
            "CREATE TYPE public.synthetic_enum AS ENUM ('one','two')",
            "SELECT oid,enumlabel,enumsortorder FROM pg_enum ORDER BY oid",
        ),
        (
            "CREATE DOMAIN public.synthetic_domain AS integer CHECK (VALUE > 0)",
            "SELECT oid,typname,typbasetype FROM pg_type WHERE typname='synthetic_domain'",
        ),
        (
            "CREATE SCHEMA synthetic_empty",
            "SELECT oid,nspname,nspowner,nspacl FROM pg_namespace WHERE nspname='synthetic_empty'",
        ),
        (
            "CREATE PUBLICATION synthetic_publication",
            "SELECT oid,pubname,pubowner FROM pg_publication",
        ),
        (
            "ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO PUBLIC",
            "SELECT oid,defaclrole,defaclnamespace,defaclobjtype,defaclacl FROM pg_default_acl",
        ),
        (
            "SELECT lo_create(1234)",
            "SELECT oid,lomowner,lomacl FROM pg_largeobject_metadata",
        ),
    ],
    ids=["enum", "domain", "empty-schema", "publication", "default-acl", "low-oid-large-object"],
)
def test_catalog_only_objects_refuse_restore(artifact, monkeypatch, create, inspect):
    archive, _ = artifact
    original = tool.pg
    restore_calls = []

    def tracked_pg(name, args, env=None):
        if name == "pg_restore" and any(arg.startswith("--dbname=") for arg in args):
            restore_calls.append(args)
        return original(name, args, env)

    monkeypatch.setattr(tool, "pg", tracked_pg)
    with disposable_database() as target:
        monkeypatch.setenv("RESTORE_DATABASE_URL", native(target))
        with psycopg.connect(native(target)) as connection:
            connection.execute(sql.SQL(create))
            expected = connection.execute(sql.SQL(inspect)).fetchall()
            assert expected
        with pytest.raises(tool.BackupError, match="non-empty"):
            tool.restore(archive, "local")
        assert restore_calls == []
        with psycopg.connect(native(target)) as connection:
            assert connection.execute(sql.SQL(inspect)).fetchall() == expected
            assert (
                connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                ).fetchall()
                == []
            )


def test_actual_late_restore_failure_rolls_back(artifact, monkeypatch, tmp_path):
    _, source = artifact
    with psycopg.connect(native(source)) as connection:
        connection.execute("SET session_replication_role=replica")
        connection.execute("UPDATE transactions SET related_transaction_id=999999 WHERE type='FEE'")
    broken = tool.backup(tmp_path / "broken", "local")
    assert tool.validate(broken)  # structural validity does not guarantee valid restored relations
    with disposable_database() as target:
        monkeypatch.setenv("RESTORE_DATABASE_URL", native(target))
        with pytest.raises(tool.BackupError, match="pg_restore failed"):
            tool.restore(broken, "local")
        with psycopg.connect(native(target)) as connection:
            assert (
                connection.execute(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public'"
                ).fetchall()[0][0]
                == 0
            )


def test_known_older_revision_forward_drill(monkeypatch, tmp_path):
    with disposable_database() as source, disposable_database() as target:
        monkeypatch.setenv("DATABASE_URL", source.render_as_string(hide_password=False))
        monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
        config = Config("alembic.ini")
        command.upgrade(config, "0001_initial_persistence")
        with psycopg.connect(native(source)) as connection:
            connection.execute(
                "INSERT INTO portfolios(name,base_currency) VALUES ('Synthetic older backup','USD')"
            )
            connection.execute(
                "INSERT INTO investment_accounts(portfolio_id,name) "
                "VALUES (1,'Synthetic older account')"
            )
            connection.execute(
                "INSERT INTO transactions(account_id,type,cash_amount,"
                "currency_code,effective_date) "
                "VALUES (1,'DEPOSIT',123.00000001,'USD','2020-01-01')"
            )
        monkeypatch.setenv("BACKUP_DATABASE_URL", native(source))
        archive = tool.backup(tmp_path / "older", "local")
        expected = facts(source)
        monkeypatch.setenv("RESTORE_DATABASE_URL", native(target))
        tool.restore(archive, "local")
        assert facts(target) == expected
        monkeypatch.setenv("DATABASE_URL", target.render_as_string(hide_password=False))
        command.upgrade(config, "head")
        command.check(config)
        assert facts(target)[0]["alembic_version"] == [(tool.HEAD,)]
        assert facts(target)[0]["transactions"] == expected[0]["transactions"]


def test_failed_backup_not_published(artifact, monkeypatch, tmp_path):
    original = tool.pg

    def fail(tool_name, args, env=None):
        if tool_name == "pg_dump" and "--format=custom" in args:
            raise tool.BackupError("synthetic dump failure")
        return original(tool_name, args, env)

    monkeypatch.setattr(tool, "pg", fail)
    output = tmp_path / "failed"
    with pytest.raises(tool.BackupError):
        tool.backup(output, "local")
    assert not list(output.iterdir())
