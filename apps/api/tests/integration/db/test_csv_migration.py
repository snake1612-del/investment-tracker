from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.integration.db.test_backup_restore import disposable_database


def test_csv_migration_additive_and_reversible(monkeypatch):
    with disposable_database() as url:
        monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
        monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
        config = Config("alembic.ini")
        command.upgrade(config, "0002_market_prices")
        engine = create_engine(url)
        try:
            before = inspect(engine)
            tables = set(before.get_table_names())
            columns = before.get_columns("transactions")
            with engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO portfolios(name,base_currency) VALUES ('Synthetic','USD')")
                )
                expected = connection.execute(text("SELECT * FROM portfolios")).fetchall()
            command.upgrade(config, "head")
            after = inspect(engine)
            assert set(after.get_table_names()) - tables == {"csv_imports"}
            assert str(after.get_columns("transactions")) == str(columns)
            assert set(c["name"] for c in after.get_columns("csv_imports")) == {
                "id",
                "account_id",
                "format_version",
                "source_fingerprint",
                "row_count",
                "created_at",
            }
            command.check(config)
            with engine.connect() as connection:
                assert connection.execute(text("SELECT * FROM portfolios")).fetchall() == expected
                assert (
                    connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0003_csv_imports"
                )
            command.downgrade(config, "0002_market_prices")
            assert set(inspect(engine).get_table_names()) == tables
            command.upgrade(config, "head")
            command.check(config)
        finally:
            engine.dispose()
