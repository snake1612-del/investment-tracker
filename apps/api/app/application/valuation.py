"""Market-price mutations and one-history-per-Account F009 orchestration."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from app.application.contracts import MarketPriceRecord, UnitOfWork
from app.application.use_cases import (
    InvalidInput,
    NotFound,
    UowFactory,
    _canonical_from_record,
    _lot_fact_from_record,
)
from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.valuation import (
    ValuationResult,
    aggregate_valuations,
    reconstruct_account_valuation,
)


def _fact(instrument_id: int, price: str, currency: str, effective_date: date) -> MarketPrice:
    try:
        return MarketPrice(instrument_id, Decimal(price), currency, effective_date)
    except (ValueError, InvalidOperation) as error:
        raise InvalidInput(str(error)) from error


def list_market_prices(factory: UowFactory, instrument_id: int) -> list[MarketPriceRecord]:
    with factory() as uow:
        if uow.instruments.get(instrument_id) is None:
            raise NotFound("Instrument not found")
        return uow.market_prices.list_for_instruments([instrument_id])


def save_market_price(
    factory: UowFactory,
    instrument_id: int,
    price: str,
    currency: str,
    effective_date: date,
    observation_id: int | None = None,
) -> MarketPriceRecord:
    with factory() as uow:
        if uow.instruments.get(instrument_id) is None:
            raise NotFound("Instrument not found")
        if (
            observation_id is not None
            and uow.market_prices.get(instrument_id, observation_id) is None
        ):
            raise NotFound("Market-price observation not found")
        fact = _fact(instrument_id, price, currency, effective_date)
        result = (
            uow.market_prices.add(fact)
            if observation_id is None
            else uow.market_prices.update(observation_id, fact)
        )
        uow.commit()
        return result


def delete_market_price(factory: UowFactory, instrument_id: int, observation_id: int) -> None:
    with factory() as uow:
        if uow.market_prices.get(instrument_id, observation_id) is None:
            raise NotFound("Market-price observation not found")
        uow.market_prices.delete(observation_id)
        uow.commit()


@dataclass(frozen=True)
class ValuationReadRecord:
    result: ValuationResult
    instrument_names: dict[int, str]


def _account(uow: UnitOfWork, account_id: int, as_of_date: date) -> ValuationResult:
    history = uow.transactions.list_for_account(account_id)
    instrument_ids = sorted(
        {record.instrument_id for record in history if record.instrument_id is not None}
    )
    prices = uow.market_prices.list_for_instruments(instrument_ids)
    return reconstruct_account_valuation(
        account_id,
        map(_canonical_from_record, history),
        map(_lot_fact_from_record, history),
        (price.fact() for price in prices),
        as_of_date,
    )


def get_valuation(
    factory: UowFactory, entity_id: int, as_of_date: date, *, portfolio: bool = False
) -> ValuationReadRecord:
    with factory() as uow:
        if portfolio:
            if uow.portfolios.get(entity_id) is None:
                raise NotFound("Portfolio not found")
            result = aggregate_valuations(
                _account(uow, account.id, as_of_date)
                for account in uow.accounts.list_for_portfolio(entity_id)
            )
        else:
            if uow.accounts.get(entity_id) is None:
                raise NotFound("Investment account not found")
            result = _account(uow, entity_id, as_of_date)
        names = {item.id: item.name for item in uow.instruments.list()}
        if any(item.instrument_id not in names for item in result.instruments):
            raise RuntimeError("Valuation Instrument metadata is missing")
        return ValuationReadRecord(result, names)
