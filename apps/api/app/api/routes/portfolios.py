from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import PortfolioCreate, PortfolioRead
from app.application.use_cases import UowFactory, create_portfolio
from app.bootstrap import get_uow_factory

router = APIRouter()


@router.post("/portfolios", status_code=status.HTTP_201_CREATED, response_model=PortfolioRead)
def post_portfolio(
    body: PortfolioCreate, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> PortfolioRead:
    return PortfolioRead.from_record(create_portfolio(factory, body.name, body.base_currency))
