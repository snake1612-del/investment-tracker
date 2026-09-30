from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import DepositCreate, PositionRead, TradeCreate, TransactionRead
from app.application.use_cases import (
    InvalidInput,
    UowFactory,
    create_buy,
    create_deposit,
    create_sell,
    get_account_positions,
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


def _trade_decimals(body: TradeCreate) -> tuple[Decimal, Decimal, Decimal]:
    try:
        return Decimal(body.quantity), Decimal(body.price), Decimal(body.cash_amount)
    except InvalidOperation as exc:
        raise InvalidInput("quantity, price and cash_amount must be decimal strings") from exc


@router.post(
    "/accounts/{account_id}/buys",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionRead,
)
def post_buy(
    account_id: int,
    body: TradeCreate,
    factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TransactionRead:
    quantity, price, cash_amount = _trade_decimals(body)
    return TransactionRead.from_record(
        create_buy(
            factory,
            account_id,
            body.instrument_id,
            quantity,
            price,
            cash_amount,
            body.currency_code,
            body.effective_date,
            body.settlement_date,
            body.note,
        )
    )


@router.post(
    "/accounts/{account_id}/sells",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionRead,
)
def post_sell(
    account_id: int,
    body: TradeCreate,
    factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TransactionRead:
    quantity, price, cash_amount = _trade_decimals(body)
    return TransactionRead.from_record(
        create_sell(
            factory,
            account_id,
            body.instrument_id,
            quantity,
            price,
            cash_amount,
            body.currency_code,
            body.effective_date,
            body.settlement_date,
            body.note,
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


@router.get("/accounts/{account_id}/positions", response_model=list[PositionRead])
def get_positions(
    account_id: int, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> list[PositionRead]:
    return [
        PositionRead.from_record(record) for record in get_account_positions(factory, account_id)
    ]
