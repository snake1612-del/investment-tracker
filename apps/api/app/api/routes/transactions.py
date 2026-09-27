from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import DepositCreate, TransactionRead
from app.application.use_cases import (
    InvalidInput,
    UowFactory,
    create_deposit,
    list_account_transactions,
)
from app.bootstrap import get_uow_factory

router = APIRouter()


@router.post(
    "/accounts/{account_id}/deposits",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionRead,
)
def post_deposit(
    account_id: int,
    body: DepositCreate,
    factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TransactionRead:
    try:
        amount = Decimal(body.cash_amount)
    except InvalidOperation as exc:
        raise InvalidInput("cash_amount must be a decimal string") from exc
    return TransactionRead.from_record(
        create_deposit(
            factory, account_id, amount, body.currency_code, body.effective_date, body.note
        )
    )


@router.get("/accounts/{account_id}/transactions", response_model=list[TransactionRead])
def get_transactions(
    account_id: int, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> list[TransactionRead]:
    return [
        TransactionRead.from_record(record)
        for record in list_account_transactions(factory, account_id)
    ]
