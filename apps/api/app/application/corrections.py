"""F006 mutations of current canonical facts; derived state is reconstructed on read."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.cash import validate_cash_context
from app.application.contracts import TransactionRecord, UnitOfWork
from app.application.use_cases import InvalidInput, NotFound, UowFactory
from app.domain.transactions import CanonicalTransaction, TransactionType


@dataclass(frozen=True)
class DepositCorrection:
    effective_date: date
    currency_code: str
    cash_amount: Decimal


@dataclass(frozen=True)
class TradeCorrection:
    instrument_id: int
    effective_date: date
    currency_code: str
    quantity: Decimal
    price: Decimal
    cash_amount: Decimal
    settlement_date: date | None


@dataclass(frozen=True)
class IncomeCorrection:
    instrument_id: int
    effective_date: date
    currency_code: str
    cash_amount: Decimal


@dataclass(frozen=True)
class ChargeCorrection:
    instrument_id: int | None
    related_transaction_id: int | None
    effective_date: date
    currency_code: str
    cash_amount: Decimal


def _manual_record(uow: UnitOfWork, account_id: int, transaction_id: int) -> TransactionRecord:
    if uow.accounts.get(account_id) is None:
        raise NotFound("Investment account not found")
    record = uow.transactions.get_for_account(account_id, transaction_id)
    if record is None:
        raise NotFound("Transaction not found")
    if record.type not in set(TransactionType):
        raise InvalidInput("Unsupported manual transaction type")
    return record


def update_manual_transaction(
    factory: UowFactory,
    account_id: int,
    transaction_id: int,
    correction: DepositCorrection | TradeCorrection | IncomeCorrection | ChargeCorrection,
) -> TransactionRecord:
    with factory() as uow:
        record = _manual_record(uow, account_id, transaction_id)
        if record.type in {TransactionType.DEPOSIT, TransactionType.WITHDRAWAL}:
            if not isinstance(correction, DepositCorrection):
                raise InvalidInput("External flow requires complete cash factual state")
            flow_constructor = (
                CanonicalTransaction.deposit
                if record.type is TransactionType.DEPOSIT
                else CanonicalTransaction.withdrawal
            )
            facts = flow_constructor(
                account_id,
                correction.cash_amount,
                correction.currency_code,
                correction.effective_date,
                record.note,
            )
        elif record.type in {TransactionType.BUY, TransactionType.SELL}:
            if not isinstance(correction, TradeCorrection):
                raise InvalidInput("BUY/SELL requires complete trade factual state")
            if uow.instruments.get(correction.instrument_id) is None:
                raise NotFound("Instrument not found")
            constructor = (
                CanonicalTransaction.buy
                if record.type is TransactionType.BUY
                else CanonicalTransaction.sell
            )
            facts = constructor(
                account_id,
                correction.instrument_id,
                correction.quantity,
                correction.price,
                correction.cash_amount,
                correction.currency_code,
                correction.effective_date,
                correction.settlement_date,
                record.note,
            )
        elif record.type in {TransactionType.DIVIDEND, TransactionType.COUPON}:
            if not isinstance(correction, IncomeCorrection):
                raise InvalidInput("Income requires complete income factual state")
            validate_cash_context(uow, account_id, correction.instrument_id)
            income_constructor = (
                CanonicalTransaction.dividend
                if record.type is TransactionType.DIVIDEND
                else CanonicalTransaction.coupon
            )
            facts = income_constructor(
                account_id,
                correction.instrument_id,
                correction.cash_amount,
                correction.currency_code,
                correction.effective_date,
                record.note,
            )
        else:
            if not isinstance(correction, ChargeCorrection):
                raise InvalidInput("Fee/Tax requires complete charge factual state")
            validate_cash_context(
                uow,
                account_id,
                correction.instrument_id,
                correction.related_transaction_id,
                transaction_id,
            )
            charge_constructor = (
                CanonicalTransaction.fee
                if record.type is TransactionType.FEE
                else CanonicalTransaction.tax
            )
            facts = charge_constructor(
                account_id,
                correction.cash_amount,
                correction.currency_code,
                correction.effective_date,
                correction.instrument_id,
                correction.related_transaction_id,
                record.note,
            )
        result = uow.transactions.update_facts(transaction_id, facts)
        uow.commit()
        return result


def delete_manual_transaction(factory: UowFactory, account_id: int, transaction_id: int) -> None:
    with factory() as uow:
        _manual_record(uow, account_id, transaction_id)
        uow.transactions.delete_for_account(account_id, transaction_id)
        uow.commit()
