"""Lossless F009 transport; all financial decisions are domain-owned."""

from datetime import date, datetime
from typing import Annotated, Literal, TypedDict

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import ExactMoneyRead
from app.application.contracts import MarketPriceRecord
from app.application.use_cases import UowFactory
from app.application.valuation import (
    ValuationReadRecord,
    delete_market_price,
    get_valuation,
    list_market_prices,
    save_market_price,
)
from app.bootstrap import get_uow_factory
from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.valuation import ValuationReason

router = APIRouter()
Factory = Annotated[UowFactory, Depends(get_uow_factory)]


class MarketPriceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: Annotated[str, Field(strict=True, max_length=256)]
    currency_code: Annotated[str, Field(strict=True, pattern=r"^[A-Z]{3}$")]
    effective_date: date


class SelectedPriceRead(BaseModel):
    price: str
    currency_code: str
    effective_date: date

    @classmethod
    def from_fact(cls, fact: MarketPrice) -> SelectedPriceRead:
        return cls(
            price=format(fact.price, "f"),
            currency_code=fact.currency_code,
            effective_date=fact.effective_date,
        )


class MarketPriceRead(SelectedPriceRead):
    id: int
    instrument_id: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: MarketPriceRecord) -> MarketPriceRead:
        rendered = format(record.price, "f")
        rendered = rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
        return cls(**{**record.__dict__, "price": rendered})


class UnresolvedBase(BaseModel):
    account_id: int
    instrument_id: int
    instrument_name: str
    quantity: str


class UnresolvedIdentity(TypedDict):
    account_id: int
    instrument_id: int
    instrument_name: str
    quantity: str


class MissingPriceRead(UnresolvedBase):
    reason: Literal["MISSING_MARKET_PRICE"] = "MISSING_MARKET_PRICE"


class IncompleteBasisRead(UnresolvedBase):
    reason: Literal["MISSING_ACQUISITION_BASIS"] = "MISSING_ACQUISITION_BASIS"
    market_value_component: ExactMoneyRead | None


class NegativePositionRead(UnresolvedBase):
    reason: Literal["UNSUPPORTED_NEGATIVE_POSITION"] = "UNSUPPORTED_NEGATIVE_POSITION"
    market_value_component: ExactMoneyRead | None


class MismatchRead(UnresolvedBase):
    reason: Literal["CURRENCY_MISMATCH"] = "CURRENCY_MISMATCH"
    market_value_component: ExactMoneyRead
    remaining_basis: ExactMoneyRead


type UnresolvedRead = Annotated[
    MissingPriceRead | IncompleteBasisRead | NegativePositionRead | MismatchRead,
    Field(discriminator="reason"),
]


class InstrumentValuationRead(BaseModel):
    account_id: int
    instrument_id: int
    instrument_name: str
    quantity: str
    selected_market_price: SelectedPriceRead | None
    market_value: ExactMoneyRead | None
    resolved_unrealised_pnl_by_currency: list[ExactMoneyRead]
    unresolved_components: list[UnresolvedRead]
    is_fully_resolved: bool


class ValuationRead(BaseModel):
    metric: Literal["SECURITY_VALUATION_AND_UNREALISED_PNL"] = (
        "SECURITY_VALUATION_AND_UNREALISED_PNL"
    )
    as_of_date: date
    resolved_market_value_by_currency: list[ExactMoneyRead]
    resolved_unrealised_pnl_by_currency: list[ExactMoneyRead]
    instruments: list[InstrumentValuationRead]
    is_fully_resolved: bool

    @classmethod
    def from_record(cls, record: ValuationReadRecord, as_of_date: date) -> ValuationRead:
        instruments: list[InstrumentValuationRead] = []
        for item in record.result.instruments:
            unresolved: list[UnresolvedRead] = []
            for component in item.unresolved_components:
                common: UnresolvedIdentity = {
                    "account_id": component.account_id,
                    "instrument_id": component.instrument_id,
                    "instrument_name": record.instrument_names[component.instrument_id],
                    "quantity": str(component.quantity),
                }
                marked = (
                    ExactMoneyRead.from_money(component.market_value_component)
                    if component.market_value_component is not None
                    else None
                )
                match component.reason:
                    case ValuationReason.MISSING_MARKET_PRICE:
                        unresolved.append(MissingPriceRead(**common))
                    case ValuationReason.MISSING_ACQUISITION_BASIS:
                        unresolved.append(
                            IncompleteBasisRead(**common, market_value_component=marked)
                        )
                    case ValuationReason.UNSUPPORTED_NEGATIVE_POSITION:
                        unresolved.append(
                            NegativePositionRead(**common, market_value_component=marked)
                        )
                    case ValuationReason.CURRENCY_MISMATCH:
                        if marked is None or component.remaining_basis is None:
                            raise RuntimeError("Incomplete currency mismatch legs")
                        unresolved.append(
                            MismatchRead(
                                **common,
                                market_value_component=marked,
                                remaining_basis=ExactMoneyRead.from_money(
                                    component.remaining_basis
                                ),
                            )
                        )
            instruments.append(
                InstrumentValuationRead(
                    account_id=item.account_id,
                    instrument_id=item.instrument_id,
                    instrument_name=record.instrument_names[item.instrument_id],
                    quantity=str(item.quantity),
                    selected_market_price=SelectedPriceRead.from_fact(item.selected_market_price)
                    if item.selected_market_price
                    else None,
                    market_value=ExactMoneyRead.from_money(item.market_value)
                    if item.market_value is not None
                    else None,
                    resolved_unrealised_pnl_by_currency=[
                        ExactMoneyRead.from_money(money)
                        for money in item.resolved_unrealised_pnl_by_currency
                    ],
                    unresolved_components=unresolved,
                    is_fully_resolved=item.is_fully_resolved,
                )
            )
        return cls(
            as_of_date=as_of_date,
            instruments=instruments,
            resolved_market_value_by_currency=[
                ExactMoneyRead.from_money(money)
                for money in record.result.resolved_market_value_by_currency
            ],
            resolved_unrealised_pnl_by_currency=[
                ExactMoneyRead.from_money(money)
                for money in record.result.resolved_unrealised_pnl_by_currency
            ],
            is_fully_resolved=record.result.is_fully_resolved,
        )


@router.post("/instruments/{instrument_id}/market-prices", status_code=201)
def create_price(instrument_id: int, body: MarketPriceRequest, factory: Factory) -> MarketPriceRead:
    return MarketPriceRead.from_record(
        save_market_price(
            factory, instrument_id, body.price, body.currency_code, body.effective_date
        )
    )


@router.get("/instruments/{instrument_id}/market-prices")
def price_history(instrument_id: int, factory: Factory) -> list[MarketPriceRead]:
    return [
        MarketPriceRead.from_record(record) for record in list_market_prices(factory, instrument_id)
    ]


@router.put("/instruments/{instrument_id}/market-prices/{observation_id}")
def update_price(
    instrument_id: int, observation_id: int, body: MarketPriceRequest, factory: Factory
) -> MarketPriceRead:
    return MarketPriceRead.from_record(
        save_market_price(
            factory,
            instrument_id,
            body.price,
            body.currency_code,
            body.effective_date,
            observation_id,
        )
    )


@router.delete("/instruments/{instrument_id}/market-prices/{observation_id}", status_code=204)
def remove_price(instrument_id: int, observation_id: int, factory: Factory) -> Response:
    delete_market_price(factory, instrument_id, observation_id)
    return Response(status_code=204)


@router.get("/accounts/{account_id}/valuation")
def account_valuation(account_id: int, as_of_date: date, factory: Factory) -> ValuationRead:
    return ValuationRead.from_record(get_valuation(factory, account_id, as_of_date), as_of_date)


@router.get("/portfolios/{portfolio_id}/valuation")
def portfolio_valuation(portfolio_id: int, as_of_date: date, factory: Factory) -> ValuationRead:
    return ValuationRead.from_record(
        get_valuation(factory, portfolio_id, as_of_date, portfolio=True), as_of_date
    )
