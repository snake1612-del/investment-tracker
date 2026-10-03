"""Strong manual cash entry contracts; no financial reconstruction during mutations."""

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.schemas import ChargeCreate, IncomeCreate, TransactionRead, WithdrawalCreate
from app.application.cash import (
    create_coupon,
    create_dividend,
    create_fee,
    create_tax,
    create_withdrawal,
)
from app.application.use_cases import InvalidInput, UowFactory
from app.bootstrap import get_uow_factory

router = APIRouter()
Factory = Annotated[UowFactory, Depends(get_uow_factory)]


def _amount(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise InvalidInput("cash_amount must be a decimal string") from exc


@router.post("/accounts/{account_id}/withdrawals", status_code=201, response_model=TransactionRead)
def post_withdrawal(account_id: int, body: WithdrawalCreate, factory: Factory) -> TransactionRead:
    return TransactionRead.from_record(
        create_withdrawal(
            factory,
            account_id,
            _amount(body.cash_amount),
            body.currency_code,
            body.effective_date,
            body.note,
        )
    )


@router.post("/accounts/{account_id}/dividends", status_code=201, response_model=TransactionRead)
def post_dividend(account_id: int, body: IncomeCreate, factory: Factory) -> TransactionRead:
    return TransactionRead.from_record(
        create_dividend(
            factory,
            account_id,
            body.instrument_id,
            _amount(body.cash_amount),
            body.currency_code,
            body.effective_date,
            body.note,
        )
    )


@router.post("/accounts/{account_id}/coupons", status_code=201, response_model=TransactionRead)
def post_coupon(account_id: int, body: IncomeCreate, factory: Factory) -> TransactionRead:
    return TransactionRead.from_record(
        create_coupon(
            factory,
            account_id,
            body.instrument_id,
            _amount(body.cash_amount),
            body.currency_code,
            body.effective_date,
            body.note,
        )
    )


@router.post("/accounts/{account_id}/fees", status_code=201, response_model=TransactionRead)
def post_fee(account_id: int, body: ChargeCreate, factory: Factory) -> TransactionRead:
    return TransactionRead.from_record(
        create_fee(
            factory,
            account_id,
            _amount(body.cash_amount),
            body.currency_code,
            body.effective_date,
            body.instrument_id,
            body.related_transaction_id,
            body.note,
        )
    )


@router.post("/accounts/{account_id}/taxes", status_code=201, response_model=TransactionRead)
def post_tax(account_id: int, body: ChargeCreate, factory: Factory) -> TransactionRead:
    return TransactionRead.from_record(
        create_tax(
            factory,
            account_id,
            _amount(body.cash_amount),
            body.currency_code,
            body.effective_date,
            body.instrument_id,
            body.related_transaction_id,
            body.note,
        )
    )
