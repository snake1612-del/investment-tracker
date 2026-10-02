"""F006 mutations of current canonical facts; derived state is reconstructed on read."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

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


def _manual_record(uow: UnitOfWork, account_id: int, transaction_id: int) -> TransactionRecord:
    if uow.accounts.get(account_id) is None:
        raise NotFound("Investment account not found")
    record = uow.transactions.get_for_account(account_id, transaction_id)
    if record is None:
        raise NotFound("Transaction not found")
    if record.type not in {TransactionType.DEPOSIT, TransactionType.BUY, TransactionType.SELL}:
        raise InvalidInput("Only manual DEPOSIT, BUY and SELL support corrections")
    return record


def update_manual_transaction(
    factory: UowFactory,
    account_id: int,
    transaction_id: int,
    correction: DepositCorrection | TradeCorrection,
) -> TransactionRecord:
    with factory() as uow:
        record = _manual_record(uow, account_id, transaction_id)
        if record.type is TransactionType.DEPOSIT:
            if not isinstance(correction, DepositCorrection):
                raise InvalidInput("DEPOSIT requires complete deposit factual state")
            facts = CanonicalTransaction.deposit(
                account_id,
                correction.cash_amount,
                correction.currency_code,
                correction.effective_date,
                record.note,
            )
        else:
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
        result = uow.transactions.update_facts(transaction_id, facts)
        uow.commit()
        return result


def delete_manual_transaction(factory: UowFactory, account_id: int, transaction_id: int) -> None:
    with factory() as uow:
        _manual_record(uow, account_id, transaction_id)
        uow.transactions.delete_for_account(account_id, transaction_id)
        uow.commit()
