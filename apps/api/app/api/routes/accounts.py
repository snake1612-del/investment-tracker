from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import AccountCreate, AccountRead, RealisedPnlRead
from app.application.use_cases import (
    UowFactory,
    create_investment_account,
    get_account_realised_pnl_read,
    list_portfolio_accounts,
)
from app.bootstrap import get_uow_factory

router = APIRouter()


@router.get("/portfolios/{portfolio_id}/accounts", response_model=list[AccountRead])
def get_accounts(
    portfolio_id: int, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> list[AccountRead]:
    return [
        AccountRead.from_record(record) for record in list_portfolio_accounts(factory, portfolio_id)
    ]


@router.post(
    "/portfolios/{portfolio_id}/accounts",
    status_code=status.HTTP_201_CREATED,
    response_model=AccountRead,
)
def post_account(
    portfolio_id: int,
    body: AccountCreate,
    factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> AccountRead:
    return AccountRead.from_record(create_investment_account(factory, portfolio_id, body.name))


@router.get("/accounts/{account_id}/realised-pnl", response_model=RealisedPnlRead)
def get_realised_pnl(
    account_id: int, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> RealisedPnlRead:
    return RealisedPnlRead.from_record(get_account_realised_pnl_read(factory, account_id))
