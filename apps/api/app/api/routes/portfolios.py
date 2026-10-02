from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import PortfolioCreate, PortfolioRead, PositionRead, RealisedPnlRead
from app.application.use_cases import (
    UowFactory,
    create_portfolio,
    get_portfolio_positions,
    get_portfolio_realised_pnl_read,
    list_portfolios,
)
from app.bootstrap import get_uow_factory

router = APIRouter()


@router.get("/portfolios", response_model=list[PortfolioRead])
def get_portfolios(factory: Annotated[UowFactory, Depends(get_uow_factory)]) -> list[PortfolioRead]:
    return [PortfolioRead.from_record(record) for record in list_portfolios(factory)]


@router.post("/portfolios", status_code=status.HTTP_201_CREATED, response_model=PortfolioRead)
def post_portfolio(
    body: PortfolioCreate, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> PortfolioRead:
    return PortfolioRead.from_record(create_portfolio(factory, body.name, body.base_currency))


@router.get("/portfolios/{portfolio_id}/positions", response_model=list[PositionRead])
def get_positions(
    portfolio_id: int, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> list[PositionRead]:
    return [
        PositionRead.from_record(record)
        for record in get_portfolio_positions(factory, portfolio_id)
    ]


@router.get("/portfolios/{portfolio_id}/realised-pnl", response_model=RealisedPnlRead)
def get_realised_pnl(
    portfolio_id: int, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> RealisedPnlRead:
    return RealisedPnlRead.from_record(get_portfolio_realised_pnl_read(factory, portfolio_id))
