"""Shared F009 latest-applicable prices and exact signed marking; no FIFO dependency."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from fractions import Fraction

from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.exact import ExactMoney, decimal_to_scaled_int


def select_prices(observations: Iterable[MarketPrice], as_of_date: date) -> dict[int, MarketPrice]:
    selected: dict[int, MarketPrice] = {}
    seen: set[tuple[int, date]] = set()
    for observation in observations:
        key = (observation.instrument_id, observation.effective_date)
        if key in seen:
            raise ValueError("Duplicate Instrument/date price facts")
        seen.add(key)
        previous = selected.get(observation.instrument_id)
        if observation.effective_date <= as_of_date and (
            previous is None or previous.effective_date < observation.effective_date
        ):
            selected[observation.instrument_id] = observation
    return selected


def marked_value(quantity: Decimal, price: MarketPrice) -> ExactMoney:
    return ExactMoney(
        Fraction(
            decimal_to_scaled_int(quantity, 12) * decimal_to_scaled_int(price.price, 12), 10**24
        ),
        price.currency_code,
    )
