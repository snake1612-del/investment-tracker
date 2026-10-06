"""Pure F010/F011 chronological reconstruction. No database, FIFO, FX or web logic."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from fractions import Fraction

from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.exact import (
    ExactMoney,
    decimal_to_scaled_int,
    scaled_int_to_decimal,
)
from app.domain.portfolio.engine.marking import marked_value, select_prices
from app.domain.portfolio.engine.money import cash_effect_units
from app.domain.portfolio.engine.positions import quantity_effect_units
from app.domain.transactions import CanonicalTransaction, TransactionType


class PerformanceReason(StrEnum):
    MISSING_MARKET_PRICE = "MISSING_MARKET_PRICE"
    MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX = "MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX"
    NON_POSITIVE_CAPITAL_BASE = "NON_POSITIVE_CAPITAL_BASE"
    ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE = "ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE"
    NEGATIVE_PERFORMANCE_VALUE = "NEGATIVE_PERFORMANCE_VALUE"
    NO_CAPITAL_AT_RISK = "NO_CAPITAL_AT_RISK"


class BenchmarkReason(StrEnum):
    UNRESOLVED_PORTFOLIO_PERFORMANCE = "UNRESOLVED_PORTFOLIO_PERFORMANCE"
    MISSING_BENCHMARK_MARKET_PRICE = "MISSING_BENCHMARK_MARKET_PRICE"
    BENCHMARK_CURRENCY_MISMATCH = "BENCHMARK_CURRENCY_MISMATCH"
    ZERO_BENCHMARK_OPENING_PRICE = "ZERO_BENCHMARK_OPENING_PRICE"
    ZERO_BENCHMARK_FLOW_EXECUTION_PRICE = "ZERO_BENCHMARK_FLOW_EXECUTION_PRICE"
    BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE = "BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE"
    ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE = "ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE"


@dataclass(frozen=True)
class Diagnostic:
    reason: PerformanceReason | BenchmarkReason
    date: date | None = None
    account_id: int | None = None
    instrument_id: int | None = None
    currencies: tuple[str, ...] = ()
    value: ExactMoney | None = None
    capital_base: ExactMoney | None = None


@dataclass(frozen=True)
class PerformanceResult:
    currency_code: str | None
    opening_value: ExactMoney | None
    closing_value: ExactMoney | None
    twr: Fraction | None
    unresolved_components: tuple[Diagnostic, ...]

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_components


@dataclass(frozen=True)
class BenchmarkResult:
    instrument_id: int
    currency_code: str | None
    opening_value: ExactMoney | None
    ending_value: ExactMoney | None
    benchmark_twr: Fraction | None
    active_return: Fraction | None
    ending_value_difference: ExactMoney | None
    unresolved_components: tuple[Diagnostic, ...]

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_components


@dataclass(frozen=True)
class PerformanceComparison:
    performance: PerformanceResult
    benchmark: BenchmarkResult | None


@dataclass(frozen=True)
class TwrOutcome:
    twr: Fraction | None
    # Date/index, reason, closing value and adjusted base; callers supply identities/currency.
    failures: tuple[tuple[int, PerformanceReason, Fraction, Fraction | None], ...]


def chain_twr(opening: Fraction, closings: Iterable[tuple[Fraction, Fraction]]) -> TwrOutcome:
    """The one F010 return engine used by both Portfolio and simulated benchmark."""
    if opening < 0:
        return TwrOutcome(
            None, ((-1, PerformanceReason.NEGATIVE_PERFORMANCE_VALUE, opening, None),)
        )
    previous = opening
    chain = Fraction(1)
    capital_at_risk = False
    failures: list[tuple[int, PerformanceReason, Fraction, Fraction | None]] = []
    for index, (value, flow) in enumerate(closings):
        base = previous + flow
        capital_at_risk |= base > 0
        if base < 0:
            failures.append((index, PerformanceReason.NON_POSITIVE_CAPITAL_BASE, value, base))
        if value < 0:
            failures.append((index, PerformanceReason.NEGATIVE_PERFORMANCE_VALUE, value, base))
        elif base == 0 and value > 0:
            failures.append(
                (index, PerformanceReason.ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE, value, base)
            )
        elif base > 0:
            chain *= value / base
        # Zero base / zero value contributes exactly one, never resets the chain.
        previous = value
    if not capital_at_risk and not failures:
        failures.append((0, PerformanceReason.NO_CAPITAL_AT_RISK, previous, Fraction(0)))
    return TwrOutcome(None if failures else chain - 1, tuple(failures))


@dataclass
class _AccountState:
    cash: dict[str, int] = field(default_factory=dict)
    quantities: dict[int, int] = field(default_factory=dict)

    def apply(self, fact: CanonicalTransaction, cash: int, quantity: int) -> None:
        self.cash[fact.currency_code] = self.cash.get(fact.currency_code, 0) + cash
        if fact.instrument_id is not None and quantity:
            self.quantities[fact.instrument_id] = (
                self.quantities.get(fact.instrument_id, 0) + quantity
            )


@dataclass(frozen=True)
class _Day:
    date: date
    value: Fraction | None
    currencies: tuple[str, ...]
    flows: dict[str, Fraction]
    prices: dict[int, MarketPrice]
    failures: tuple[Diagnostic, ...]


def _sweep(
    histories: Mapping[int, Iterable[CanonicalTransaction]],
    observations: Iterable[MarketPrice],
    start: date,
    end: date,
) -> list[_Day]:
    opening = start - timedelta(days=1)
    events: dict[date, list[tuple[int, CanonicalTransaction, int, int]]] = defaultdict(list)
    states = {account: _AccountState() for account in sorted(histories)}
    for account, history in sorted(histories.items()):
        for fact in history:
            if fact.account_id != account:
                raise ValueError("History belongs to another Account")
            cash = cash_effect_units(fact)
            quantity = quantity_effect_units(fact)
            if fact.effective_date <= opening:
                states[account].apply(fact, cash, quantity)
            elif fact.effective_date <= end:
                events[fact.effective_date].append((account, fact, cash, quantity))
    observations = tuple(observations)
    # Validate duplicate facts including future observations, exactly as F009 does.
    select_prices(observations, end)
    prices = select_prices(observations, opening)
    price_events: dict[date, list[MarketPrice]] = defaultdict(list)
    for price in observations:
        if opening < price.effective_date <= end:
            price_events[price.effective_date].append(price)
    days: list[_Day] = []
    day = opening
    while day <= end:
        flows: dict[str, Fraction] = {}
        for account, fact, cash, quantity in events.get(day, ()):
            states[account].apply(fact, cash, quantity)
            if fact.type in {TransactionType.DEPOSIT, TransactionType.WITHDRAWAL}:
                flows[fact.currency_code] = flows.get(fact.currency_code, Fraction(0)) + Fraction(
                    cash, 10**8
                )
        if day in price_events:
            prices = select_prices((*prices.values(), *price_events[day]), day)
        currencies: set[str] = {currency for currency, flow in flows.items() if flow}
        total = Fraction(0)
        failures: list[Diagnostic] = []
        # Never net positions across Accounts before marking: offsets cannot hide missing prices.
        for account, state in states.items():
            currencies.update(currency for currency, units in state.cash.items() if units)
            total += sum((Fraction(units, 10**8) for units in state.cash.values()), Fraction(0))
            for instrument, units in sorted(state.quantities.items()):
                if not units:
                    continue
                price = prices.get(instrument)
                if price is None:
                    failures.append(
                        Diagnostic(PerformanceReason.MISSING_MARKET_PRICE, day, account, instrument)
                    )
                else:
                    marked = marked_value(scaled_int_to_decimal(units, 12), price)
                    currencies.add(marked.currency_code)
                    total += marked.amount
        if len(currencies) > 1:
            failures.append(
                Diagnostic(
                    PerformanceReason.MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX,
                    day,
                    currencies=tuple(sorted(currencies)),
                )
            )
        days.append(
            _Day(
                day,
                None if failures else total,
                tuple(sorted(currencies)),
                flows,
                prices,
                tuple(failures),
            )
        )
        if day == end:
            break
        day += timedelta(days=1)
    return days


def _money(value: Fraction | None, currency: str | None) -> ExactMoney | None:
    return ExactMoney(value, currency) if value is not None and currency is not None else None


def reconstruct_performance(
    histories: Mapping[int, Iterable[CanonicalTransaction]],
    observations: Iterable[MarketPrice],
    start_date: date,
    end_date: date,
    benchmark_instrument_id: int | None = None,
) -> PerformanceComparison:
    if start_date <= date.min or start_date > end_date:
        raise ValueError("Period requires an opening date and start_date <= end_date")
    days = _sweep(histories, observations, start_date, end_date)
    currencies = tuple(sorted({currency for day in days for currency in day.currencies}))
    currency = currencies[0] if len(currencies) == 1 else None
    failures = [failure for day in days for failure in day.failures]
    if len(currencies) > 1 and not any(
        failure.reason == PerformanceReason.MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX
        for failure in failures
    ):
        failures.append(
            Diagnostic(
                PerformanceReason.MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX, currencies=currencies
            )
        )
    twr = None
    opening = days[0].value
    if opening is not None and opening < 0:
        failures.append(
            Diagnostic(
                PerformanceReason.NEGATIVE_PERFORMANCE_VALUE,
                days[0].date,
                value=_money(opening, currency),
            )
        )
    if not failures and opening is not None:
        outcome = chain_twr(
            opening,
            (
                (day.value, sum(day.flows.values(), Fraction(0)))
                for day in days[1:]
                if day.value is not None
            ),
        )
        twr = outcome.twr
        failures.extend(
            Diagnostic(
                reason,
                days[index + 1].date,
                value=_money(value, currency),
                capital_base=_money(base, currency),
            )
            for index, reason, value, base in outcome.failures
        )
    performance = PerformanceResult(
        currency, _money(opening, currency), _money(days[-1].value, currency), twr, tuple(failures)
    )
    benchmark = (
        _benchmark(performance, days, benchmark_instrument_id)
        if benchmark_instrument_id is not None
        else None
    )
    return PerformanceComparison(performance, benchmark)


def _benchmark(
    performance: PerformanceResult, days: list[_Day], instrument: int
) -> BenchmarkResult:
    currency = performance.currency_code
    opening = performance.opening_value
    ending: ExactMoney | None = None
    failures: list[Diagnostic] = []

    def fail(
        reason: BenchmarkReason,
        day: date,
        value: Fraction | None = None,
        base: Fraction | None = None,
    ) -> None:
        failures.append(
            Diagnostic(
                reason,
                day,
                instrument_id=instrument,
                value=_money(value, currency),
                capital_base=_money(base, currency),
            )
        )

    def price_at(day: _Day, zero_reason: BenchmarkReason | None = None) -> Fraction | None:
        price = day.prices.get(instrument)
        if price is None:
            fail(BenchmarkReason.MISSING_BENCHMARK_MARKET_PRICE, day.date)
            return None
        if price.currency_code != currency:
            failures.append(
                Diagnostic(
                    BenchmarkReason.BENCHMARK_CURRENCY_MISMATCH,
                    day.date,
                    instrument_id=instrument,
                    currencies=(currency, price.currency_code)
                    if currency
                    else (price.currency_code,),
                )
            )
            return None
        amount = Fraction(decimal_to_scaled_int(price.price, 12), 10**12)
        if amount == 0 and zero_reason is not None:
            fail(zero_reason, day.date)
            return None
        return amount

    twr = active = None
    difference = None
    if not performance.is_fully_resolved or opening is None:
        fail(BenchmarkReason.UNRESOLVED_PORTFOLIO_PERFORMANCE, days[1].date)
    else:
        units = Fraction(0)
        if opening.amount > 0:
            price = price_at(days[0], BenchmarkReason.ZERO_BENCHMARK_OPENING_PRICE)
            if price is not None:
                units = opening.amount / price
        values: list[tuple[Fraction, Fraction]] = []
        previous = days[0]
        for day in days[1:]:
            if failures:
                break
            flow = sum(day.flows.values(), Fraction(0))
            if flow:
                price = price_at(previous, BenchmarkReason.ZERO_BENCHMARK_FLOW_EXECUTION_PRICE)
                if price is None:
                    break
                units += flow / price
            if units < 0:
                fail(BenchmarkReason.BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE, day.date)
                break
            price = price_at(day) if units else None
            if failures:
                break
            value = units * price if price is not None else Fraction(0)
            values.append((value, flow))
            previous = day
        if not failures:
            ending = _money(values[-1][0], currency)
            outcome = chain_twr(opening.amount, values)
            for index, reason, value, base in outcome.failures:
                if reason != PerformanceReason.ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE:
                    raise RuntimeError(f"Unrepresentable benchmark TWR condition: {reason}")
                fail(
                    BenchmarkReason.ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE,
                    days[index + 1].date,
                    value,
                    base,
                )
            twr = outcome.twr
            if twr is not None and performance.twr is not None:
                active = performance.twr - twr
                if performance.closing_value is not None and ending is not None:
                    difference = performance.closing_value - ending
    return BenchmarkResult(
        instrument, currency, opening, ending, twr, active, difference, tuple(failures)
    )
