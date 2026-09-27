from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.application.use_cases import (
    create_deposit,
    create_investment_account,
    create_portfolio,
    list_account_transactions,
)
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def test_migration_creates_only_initial_tables(test_session_factory: sessionmaker[Session]) -> None:
    engine = test_session_factory.kw["bind"]
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "portfolios",
        "investment_accounts",
        "instruments",
        "transactions",
    }
    assert {index["name"] for index in inspector.get_indexes("investment_accounts")} == {
        "ix_investment_accounts_portfolio_id"
    }
    assert {index["name"] for index in inspector.get_indexes("transactions")} == {
        "ix_transactions_account_id"
    }


def test_portfolio_account_deposit_round_trip(clean_db: sessionmaker[Session]) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    deposit = create_deposit(
        factory, account.id, Decimal("123456.12500001"), "USD", date(2026, 9, 27)
    )
    listed = list_account_transactions(factory, account.id)

    assert portfolio.id > 0 and account.id > 0 and deposit.id > 0
    assert account.portfolio_id == portfolio.id
    assert listed == [deposit]
    assert listed[0].cash_amount == Decimal("123456.12500001")
    assert listed[0].effective_date == date(2026, 9, 27)


def test_foreign_keys_and_canonical_constraints(clean_db: sessionmaker[Session]) -> None:
    with clean_db() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text("INSERT INTO investment_accounts (portfolio_id, name) VALUES (999, 'orphan')")
            )
            session.commit()
        session.rollback()

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    with clean_db() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO transactions "
                    "(account_id, type, cash_amount, currency_code, effective_date) "
                    "VALUES (:account_id, 'DEPOSIT', -1, 'USD', DATE '2026-09-27')"
                ),
                {"account_id": account.id},
            )
            session.commit()
