"""Type-specific manual cash events and canonical Fee/Tax relation validation."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from app.application.contracts import TransactionRecord, UnitOfWork
from app.application.use_cases import InvalidInput, NotFound, UowFactory
from app.domain.transactions import CanonicalTransaction, TransactionType


def validate_cash_context(
    uow: UnitOfWork,
    account_id: int,
    instrument_id: int | None,
    related_transaction_id: int | None = None,
    transaction_id: int | None = None,
) -> None:
    if instrument_id is not None and uow.instruments.get(instrument_id) is None:
        raise NotFound("Instrument not found")
    if related_transaction_id is None:
        return
    if related_transaction_id == transaction_id:
        raise InvalidInput("A transaction cannot relate to itself")
    parent = uow.transactions.get_for_account(account_id, related_transaction_id)
    if parent is None:
        raise NotFound("Related transaction not found")
    if parent.type in {TransactionType.FEE, TransactionType.TAX}:
        raise InvalidInput("Fee and Tax cannot be relation parents")
    if (
        instrument_id is not None
        and parent.instrument_id is not None
        and (instrument_id != parent.instrument_id)
    ):
        raise InvalidInput("Instrument must match the related transaction Instrument")


def _persist(
    factory: UowFactory,
    account_id: int,
    instrument_id: int | None,
    related_transaction_id: int | None,
    constructor: Callable[[], CanonicalTransaction],
) -> TransactionRecord:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        validate_cash_context(uow, account_id, instrument_id, related_transaction_id)
        record = uow.transactions.add(constructor())
        uow.commit()
        return record


def create_withdrawal(
    factory: UowFactory,
    account_id: int,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    note: str | None = None,
) -> TransactionRecord:
    return _persist(
        factory,
        account_id,
        None,
        None,
        lambda: CanonicalTransaction.withdrawal(
            account_id, cash_amount, currency_code, effective_date, note
        ),
    )


def create_dividend(
    factory: UowFactory,
    account_id: int,
    instrument_id: int,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    note: str | None = None,
) -> TransactionRecord:
    return _persist(
        factory,
        account_id,
        instrument_id,
        None,
        lambda: CanonicalTransaction.dividend(
            account_id, instrument_id, cash_amount, currency_code, effective_date, note
        ),
    )


def create_coupon(
    factory: UowFactory,
    account_id: int,
    instrument_id: int,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    note: str | None = None,
) -> TransactionRecord:
    return _persist(
        factory,
        account_id,
        instrument_id,
        None,
        lambda: CanonicalTransaction.coupon(
            account_id, instrument_id, cash_amount, currency_code, effective_date, note
        ),
    )


def create_fee(
    factory: UowFactory,
    account_id: int,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    instrument_id: int | None = None,
    related_transaction_id: int | None = None,
    note: str | None = None,
) -> TransactionRecord:
    return _persist(
        factory,
        account_id,
        instrument_id,
        related_transaction_id,
        lambda: CanonicalTransaction.fee(
            account_id,
            cash_amount,
            currency_code,
            effective_date,
            instrument_id,
            related_transaction_id,
            note,
        ),
    )


def create_tax(
    factory: UowFactory,
    account_id: int,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    instrument_id: int | None = None,
    related_transaction_id: int | None = None,
    note: str | None = None,
) -> TransactionRecord:
    return _persist(
        factory,
        account_id,
        instrument_id,
        related_transaction_id,
        lambda: CanonicalTransaction.tax(
            account_id,
            cash_amount,
            currency_code,
            effective_date,
            instrument_id,
            related_transaction_id,
            note,
        ),
    )
