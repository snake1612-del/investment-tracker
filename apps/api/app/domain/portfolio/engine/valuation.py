"""Exact F009 security valuation; no web, SQL, FX or realised-P&L dependency."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction

from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.exact import decimal_to_scaled_int
from app.domain.portfolio.engine.fifo import ExactMoney, LotTransactionFact, reconstruct_fifo_lots
from app.domain.portfolio.engine.positions import reconstruct_positions
from app.domain.transactions import CanonicalTransaction


class ValuationReason(StrEnum):
    MISSING_MARKET_PRICE = "MISSING_MARKET_PRICE"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    MISSING_ACQUISITION_BASIS = "MISSING_ACQUISITION_BASIS"
    UNSUPPORTED_NEGATIVE_POSITION = "UNSUPPORTED_NEGATIVE_POSITION"


@dataclass(frozen=True)
class ValuationUnresolved:
    account_id: int
    instrument_id: int
    quantity: Decimal
    reason: ValuationReason
    market_value_component: ExactMoney | None = None
    remaining_basis: ExactMoney | None = None


@dataclass(frozen=True)
class InstrumentValuation:
    account_id: int
    instrument_id: int
    quantity: Decimal
    selected_market_price: MarketPrice | None
    market_value: ExactMoney | None
    resolved_unrealised_pnl_by_currency: tuple[ExactMoney, ...]
    unresolved_components: tuple[ValuationUnresolved, ...]

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_components


@dataclass(frozen=True)
class ValuationResult:
    instruments: tuple[InstrumentValuation, ...]
    resolved_market_value_by_currency: tuple[ExactMoney, ...]
    resolved_unrealised_pnl_by_currency: tuple[ExactMoney, ...]

    @property
    def is_fully_resolved(self) -> bool:
        return all(item.is_fully_resolved for item in self.instruments)


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


def _marked(quantity: Decimal, price: MarketPrice) -> ExactMoney:
    return ExactMoney(
        Fraction(
            decimal_to_scaled_int(quantity, 12) * decimal_to_scaled_int(price.price, 12), 10**24
        ),
        price.currency_code,
    )


def _totals(values: Iterable[ExactMoney]) -> tuple[ExactMoney, ...]:
    totals: dict[str, ExactMoney] = {}
    for value in values:
        currency = value.currency_code
        totals[currency] = totals.get(currency, ExactMoney(Fraction(0), currency)) + value
    return tuple(totals[currency] for currency in sorted(totals))


def reconstruct_account_valuation(
    account_id: int,
    transactions: Iterable[CanonicalTransaction],
    lot_facts: Iterable[LotTransactionFact],
    observations: Iterable[MarketPrice],
    as_of_date: date,
) -> ValuationResult:
    """F003 + as-of F004 + F009; independent limitations remain independent."""
    quantities = reconstruct_positions(transactions, as_of_date)
    fifo = reconstruct_fifo_lots(
        (fact for fact in lot_facts if fact.effective_date <= as_of_date), account_id=account_id
    )
    prices = select_prices(observations, as_of_date)
    instruments: list[InstrumentValuation] = []
    for instrument_id, quantity in sorted(quantities.items()):
        if quantity == 0:
            continue
        price = prices.get(instrument_id)
        value = _marked(quantity, price) if price else None
        unresolved: list[ValuationUnresolved] = []
        resolved: list[ExactMoney] = []
        if price is None:
            unresolved.append(
                ValuationUnresolved(
                    account_id, instrument_id, quantity, ValuationReason.MISSING_MARKET_PRICE
                )
            )
        if quantity < 0:
            unresolved.append(
                ValuationUnresolved(
                    account_id,
                    instrument_id,
                    quantity,
                    ValuationReason.UNSUPPORTED_NEGATIVE_POSITION,
                    value,
                )
            )
        elif any(sell.instrument_id == instrument_id for sell in fifo.unmatched_sells):
            unresolved.append(
                ValuationUnresolved(
                    account_id,
                    instrument_id,
                    quantity,
                    ValuationReason.MISSING_ACQUISITION_BASIS,
                    value,
                )
            )
        elif price is not None:
            for lot in fifo.open_lots:
                if lot.instrument_id != instrument_id:
                    continue
                marked = _marked(lot.remaining_quantity, price)
                if lot.remaining_basis.currency_code == price.currency_code:
                    resolved.append(marked - lot.remaining_basis)
                else:
                    unresolved.append(
                        ValuationUnresolved(
                            account_id,
                            instrument_id,
                            lot.remaining_quantity,
                            ValuationReason.CURRENCY_MISMATCH,
                            marked,
                            lot.remaining_basis,
                        )
                    )
        instruments.append(
            InstrumentValuation(
                account_id,
                instrument_id,
                quantity,
                price,
                value,
                _totals(resolved),
                tuple(unresolved),
            )
        )
    return aggregate_valuations((ValuationResult(tuple(instruments), (), ()),))


def aggregate_valuations(accounts: Iterable[ValuationResult]) -> ValuationResult:
    """Keep Account contributions (including offsetting positions) visible, aggregate money only."""
    instruments = tuple(item for account in accounts for item in account.instruments)
    return ValuationResult(
        instruments,
        _totals(item.market_value for item in instruments if item.market_value is not None),
        _totals(
            money for item in instruments for money in item.resolved_unrealised_pnl_by_currency
        ),
    )
