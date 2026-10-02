from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.schemas import (
    DepositCorrectionRequest,
    DepositCreate,
    PositionRead,
    TradeCorrectionRequest,
    TradeCreate,
    TransactionRead,
)
from app.application.corrections import (
    DepositCorrection,
    TradeCorrection,
    delete_manual_transaction,
    update_manual_transaction,
)
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


@router.put("/accounts/{account_id}/transactions/{transaction_id}", response_model=TransactionRead)
def put_transaction(
    account_id: int,
    transaction_id: int,
    body: TradeCorrectionRequest | DepositCorrectionRequest,
    factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TransactionRead:
    try:
        correction = (
            TradeCorrection(
                body.instrument_id,
                body.effective_date,
                body.currency_code,
                Decimal(body.quantity),
                Decimal(body.price),
                Decimal(body.cash_amount),
                body.settlement_date,
            )
            if isinstance(body, TradeCorrectionRequest)
            else DepositCorrection(
                body.effective_date, body.currency_code, Decimal(body.cash_amount)
            )
        )
    except InvalidOperation as exc:
        raise InvalidInput("Financial values must be decimal strings") from exc
    return TransactionRead.from_record(
        update_manual_transaction(factory, account_id, transaction_id, correction)
    )


@router.delete("/accounts/{account_id}/transactions/{transaction_id}", status_code=204)
def delete_transaction(
    account_id: int,
    transaction_id: int,
    factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> Response:
    delete_manual_transaction(factory, account_id, transaction_id)
    return Response(status_code=204)


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
