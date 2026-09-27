from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import AccountCreate, AccountRead
from app.application.use_cases import UowFactory, create_investment_account
from app.bootstrap import get_uow_factory

router = APIRouter()


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
