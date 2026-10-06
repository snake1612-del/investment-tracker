from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


def test_frozen_market_price_schema(test_session_factory: sessionmaker[Session]):
    inspector = inspect(test_session_factory.kw["bind"])
    columns = {item["name"]: item for item in inspector.get_columns("market_price_observations")}
    assert set(columns) == {
        "id",
        "instrument_id",
        "price",
        "currency_code",
        "effective_date",
        "created_at",
        "updated_at",
    }
    assert columns["price"]["type"].precision == 28
    assert columns["price"]["type"].scale == 12
    assert columns["id"].get("identity") is not None
    assert all(not item["nullable"] for item in columns.values())
    assert inspector.get_unique_constraints("market_price_observations")[0]["column_names"] == [
        "instrument_id",
        "effective_date",
    ]
    assert (
        inspector.get_foreign_keys("market_price_observations")[0]["options"]["ondelete"]
        == "RESTRICT"
    )


@pytest.mark.parametrize(
    "price,currency,instrument", [("-1", "USD", 1), ("1", "usd", 1), ("1", "USD", 999)]
)
def test_database_constraints_not_only_http_validation(
    clean_db: sessionmaker[Session], price: str, currency: str, instrument: int
):
    with clean_db() as session:
        session.execute(text("INSERT INTO instruments (name) VALUES ('Fund')"))
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO market_price_observations "
                    "(instrument_id, price, currency_code, effective_date) "
                    "VALUES (:instrument, :price, :currency, '2020-01-01')"
                ),
                dict(instrument=instrument, price=Decimal(price), currency=currency),
            )
            session.commit()


def test_instrument_delete_restricted_by_price_history(clean_db: sessionmaker[Session]):
    with clean_db() as session:
        session.execute(text("INSERT INTO instruments (name) VALUES ('Fund')"))
        session.execute(
            text(
                "INSERT INTO market_price_observations "
                "(instrument_id, price, currency_code, effective_date) "
                "VALUES (1, 0, 'USD', '2020-01-01')"
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(text("DELETE FROM instruments WHERE id=1"))
            session.commit()
