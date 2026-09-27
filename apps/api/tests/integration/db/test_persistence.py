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


def test_account_foreign_key_rejects_orphan(clean_db: sessionmaker[Session]) -> None:
    with clean_db() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text("INSERT INTO investment_accounts (portfolio_id, name) VALUES (999, 'orphan')")
            )
            session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "UNKNOWN"},
        {"cash_amount": Decimal("-1")},
        {"quantity": Decimal("-1")},
        {"price": Decimal("-1")},
        {"currency_code": "usd"},
    ],
)
def test_transaction_universal_constraints_reject_invalid_values(
    clean_db: sessionmaker[Session], overrides: dict[str, str | Decimal]
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    values: dict[str, str | Decimal | int] = {
        "account_id": account.id,
        "type": "DEPOSIT",
        "quantity": Decimal("1"),
        "price": Decimal("1"),
        "cash_amount": Decimal("1"),
        "currency_code": "USD",
    }
    values.update(overrides)

    with clean_db() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO transactions "
                    "(account_id, type, quantity, price, cash_amount, currency_code, "
                    "effective_date) "
                    "VALUES (:account_id, :type, :quantity, :price, :cash_amount, "
                    ":currency_code, DATE '2026-09-27')"
                ),
                values,
            )
            session.commit()


def test_related_transaction_self_reference_and_restrict_delete(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    origin = create_deposit(factory, account.id, Decimal("100"), "USD", date(2026, 9, 27))

    with clean_db() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO transactions "
                    "(id, account_id, related_transaction_id, type, cash_amount, "
                    "currency_code, effective_date) "
                    "VALUES (1000, :account_id, 1000, 'FEE', 1, 'USD', DATE '2026-09-27')"
                ),
                {"account_id": account.id},
            )
            session.commit()

    with clean_db() as session:
        child_id = session.execute(
            text(
                "INSERT INTO transactions "
                "(account_id, related_transaction_id, type, cash_amount, currency_code, "
                "effective_date) "
                "VALUES (:account_id, :origin_id, 'FEE', 1, 'USD', DATE '2026-09-27') "
                "RETURNING id"
            ),
            {"account_id": account.id, "origin_id": origin.id},
        ).scalar_one()
        session.commit()

    with clean_db() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text("DELETE FROM transactions WHERE id = :origin_id"), {"origin_id": origin.id}
            )
            session.commit()

    with clean_db() as session:
        rows = session.execute(
            text("SELECT id, related_transaction_id FROM transactions ORDER BY id")
        ).all()
        assert rows == [(origin.id, None), (child_id, origin.id)]


def test_concrete_uow_rolls_back_all_uncommitted_repository_work(
    clean_db: sessionmaker[Session],
) -> None:
    with pytest.raises(RuntimeError, match="abort use case"):
        with SqlAlchemyUnitOfWork(clean_db) as uow:
            portfolio = uow.portfolios.add("Uncommitted", "USD")
            account = uow.accounts.add(portfolio.id, "Uncommitted account")
            assert uow.portfolios.get(portfolio.id) == portfolio
            assert uow.accounts.get(account.id) == account
            raise RuntimeError("abort use case")

    with clean_db() as session:
        assert (
            session.execute(
                text("SELECT count(*) FROM portfolios WHERE name = 'Uncommitted'")
            ).scalar_one()
            == 0
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM investment_accounts WHERE name = 'Uncommitted account'")
            ).scalar_one()
            == 0
        )
