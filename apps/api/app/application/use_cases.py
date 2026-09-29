"""Typed use-case functions for the first persistence vertical slice."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    PortfolioRecord,
    TransactionRecord,
    UnitOfWork,
)
from app.domain.instruments import normalized_instrument_name
from app.domain.transactions import CanonicalTransaction, TransactionType, valid_currency_code


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


def create_instrument(factory: UowFactory, name: str) -> InstrumentRecord:
    trimmed_name = normalized_instrument_name(name)
    with factory() as uow:
        result = uow.instruments.add(trimmed_name)
        uow.commit()
        return result


def list_instruments(factory: UowFactory) -> list[InstrumentRecord]:
    with factory() as uow:
        return uow.instruments.list()


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


def create_buy(
    factory: UowFactory,
    account_id: int,
    instrument_id: int,
    quantity: Decimal,
    price: Decimal,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    settlement_date: date | None = None,
    note: str | None = None,
) -> TransactionRecord:
    return _create_manual_trade(
        factory,
        TransactionType.BUY,
        account_id,
        instrument_id,
        quantity,
        price,
        cash_amount,
        currency_code,
        effective_date,
        settlement_date,
        note,
    )


def create_sell(
    factory: UowFactory,
    account_id: int,
    instrument_id: int,
    quantity: Decimal,
    price: Decimal,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    settlement_date: date | None = None,
    note: str | None = None,
) -> TransactionRecord:
    return _create_manual_trade(
        factory,
        TransactionType.SELL,
        account_id,
        instrument_id,
        quantity,
        price,
        cash_amount,
        currency_code,
        effective_date,
        settlement_date,
        note,
    )


def _create_manual_trade(
    factory: UowFactory,
    trade_type: TransactionType,
    account_id: int,
    instrument_id: int,
    quantity: Decimal,
    price: Decimal,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    settlement_date: date | None,
    note: str | None,
) -> TransactionRecord:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        if uow.instruments.get(instrument_id) is None:
            raise NotFound("Instrument not found")
        constructor = (
            CanonicalTransaction.buy
            if trade_type is TransactionType.BUY
            else CanonicalTransaction.sell
        )
        transaction = constructor(
            account_id,
            instrument_id,
            quantity,
            price,
            cash_amount,
            currency_code,
            effective_date,
            settlement_date,
            note,
        )
        result = uow.transactions.add(transaction)
        uow.commit()
        return result


def list_account_transactions(factory: UowFactory, account_id: int) -> list[TransactionRecord]:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        return uow.transactions.list_for_account(account_id)
