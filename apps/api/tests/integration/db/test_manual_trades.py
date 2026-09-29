from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.application.use_cases import (
    create_buy,
    create_instrument,
    create_investment_account,
    create_portfolio,
    create_sell,
    list_account_transactions,
    list_instruments,
)
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def test_instrument_repository_add_get_list_and_duplicates(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    first = create_instrument(factory, "Same")
    second = create_instrument(factory, "Same")
    assert first.id < second.id
    assert [item.id for item in list_instruments(factory)] == [first.id, second.id]
    with factory() as uow:
        assert uow.instruments.get(first.id) == first
        assert uow.instruments.get(999) is None


def test_buy_sell_persist_exact_facts_and_optional_settlement(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    instrument = create_instrument(factory, "Share")
    buy = create_buy(
        factory,
        account.id,
        instrument.id,
        Decimal("1.000000000001"),
        Decimal("10.000000000001"),
        Decimal("9.99999999"),
        "USD",
        date(2020, 1, 2),
    )
    sell = create_sell(
        factory,
        account.id,
        instrument.id,
        Decimal("2"),
        Decimal("11"),
        Decimal("21.99999999"),
        "USD",
        date(2019, 1, 2),
        date(2019, 1, 3),
    )
    listed = list_account_transactions(factory, account.id)
    assert listed == [buy, sell]
    assert buy.quantity == Decimal("1.000000000001")
    assert buy.price == Decimal("10.000000000001")
    assert buy.cash_amount == Decimal("9.99999999")
    assert buy.settlement_date is None
    assert sell.cash_amount == Decimal("21.99999999")
    assert sell.settlement_date == date(2019, 1, 3)
    assert sell.quantity is not None and buy.quantity is not None
    assert sell.quantity > buy.quantity  # No reconstructed-position check.
    assert sell.id > buy.id and sell.effective_date < buy.effective_date


@pytest.mark.parametrize("orphan", ["account", "instrument"])
def test_transaction_foreign_keys_reject_orphans(
    clean_db: sessionmaker[Session], orphan: str
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    instrument = create_instrument(factory, "Share")
    account_id = 999 if orphan == "account" else account.id
    instrument_id = 999 if orphan == "instrument" else instrument.id
    with clean_db() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO transactions "
                    "(account_id, instrument_id, type, quantity, price, cash_amount, "
                    "currency_code, effective_date) "
                    "VALUES (:account_id, :instrument_id, 'BUY', 1, 10, 9, 'USD', "
                    "DATE '2020-01-02')"
                ),
                {"account_id": account_id, "instrument_id": instrument_id},
            )
            session.commit()
