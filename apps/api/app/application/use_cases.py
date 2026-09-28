"""Typed use-case functions for the first persistence vertical slice."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from app.application.contracts import AccountRecord, PortfolioRecord, TransactionRecord, UnitOfWork
from app.domain.transactions import CanonicalTransaction, valid_currency_code


class NotFound(Exception):
    """A requested canonical entity does not exist."""


class InvalidInput(ValueError):
    """An application input is invalid."""


class PersistenceConflict(Exception):
    """A known persistence constraint was violated."""


UowFactory = Callable[[], UnitOfWork]


def create_portfolio(factory: UowFactory, name: str, base_currency: str) -> PortfolioRecord:
    if not name.strip() or not valid_currency_code(base_currency):
        raise InvalidInput("Portfolio name and three-letter uppercase base currency are required")
    with factory() as uow:
        result = uow.portfolios.add(name, base_currency)
        uow.commit()
        return result


def create_investment_account(factory: UowFactory, portfolio_id: int, name: str) -> AccountRecord:
    if not name.strip():
        raise InvalidInput("Investment account name is required")
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        result = uow.accounts.add(portfolio_id, name)
        uow.commit()
        return result


def create_deposit(
    factory: UowFactory,
    account_id: int,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    note: str | None = None,
) -> TransactionRecord:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        transaction = CanonicalTransaction.deposit(
            account_id, cash_amount, currency_code, effective_date, note
        )
        result = uow.transactions.add(transaction)
        uow.commit()
        return result


def list_account_transactions(factory: UowFactory, account_id: int) -> list[TransactionRecord]:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        return uow.transactions.list_for_account(account_id)
