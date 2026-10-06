from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.performance import (
    BenchmarkReason as B,
)
from app.domain.portfolio.engine.performance import (
    PerformanceReason as P,
)
from app.domain.portfolio.engine.performance import (
    chain_twr,
    reconstruct_performance,
)
from app.domain.transactions import CanonicalTransaction as T
from app.domain.transactions import TransactionType as K


def D(day):
    return date(2020, 1, day)


def fact(kind=K.DEPOSIT, cash="100", day=1, quantity="1", currency="USD", account=1):
    instrument = 1 if kind in {K.BUY, K.SELL, K.DIVIDEND, K.COUPON} else None
    trade = kind in {K.BUY, K.SELL}
    return T(
        account,
        kind,
        Decimal(cash),
        currency,
        D(day),
        instrument_id=instrument,
        quantity=Decimal(quantity) if trade else None,
        price=Decimal("999") if trade else None,
    )


def price(amount, day, instrument=1, currency="USD"):
    return MarketPrice(instrument, Decimal(amount), currency, D(day))


def calc(facts, prices=(), start=2, end=2, benchmark=None):
    return reconstruct_performance({1: facts}, prices, D(start), D(end), benchmark)


def test_negative_required_opening_cannot_be_repaired_by_first_day_flow():
    def closings():
        raise AssertionError("Negative opening must reject before calculating any growth factor")
        yield Fraction(100), Fraction(200)

    outcome = chain_twr(Fraction(-100), closings())
    assert outcome.twr is None
    assert outcome.failures == ((-1, P.NEGATIVE_PERFORMANCE_VALUE, Fraction(-100), None),)
    # No benchmark prices: unresolved Portfolio must short-circuit before unit construction.
    result = calc([fact(K.WITHDRAWAL), fact(cash="200", day=2)], benchmark=2)
    portfolio = result.performance
    assert portfolio.twr is None
    assert portfolio.opening_value is not None
    assert portfolio.closing_value is not None
    assert portfolio.opening_value.amount == -100
    assert portfolio.closing_value.amount == 100
    assert len(portfolio.unresolved_components) == 1
    diagnostic = portfolio.unresolved_components[0]
    assert diagnostic.reason == P.NEGATIVE_PERFORMANCE_VALUE
    assert diagnostic.date == D(1)
    assert diagnostic.value is not None
    assert diagnostic.value.amount == -100
    assert diagnostic.capital_base is None
    assert result.benchmark is not None
    assert result.benchmark.benchmark_twr is None
    assert result.benchmark.ending_value is None
    assert [item.reason for item in result.benchmark.unresolved_components] == [
        B.UNRESOLVED_PORTFOLIO_PERFORMANCE
    ]


@pytest.mark.parametrize(
    "opening,days,expected",
    [
        (0, [(100, 100)], Fraction(0)),
        (0, [(105, 100)], Fraction(1, 20)),
        (100, [(105, 0)], Fraction(1, 20)),
        (100, [(110, 0), (0, -110)], Fraction(1, 10)),
        (100, [(0, 0)], Fraction(-1)),
        (100, [(0, -100), (0, 0)], None),
        (0, [(0, 0)], None),
        (3, [(7, 2), (11, 0), (13, 1)], Fraction(83, 60)),
    ],
)
def test_one_exact_twr_engine(opening, days, expected):
    with localcontext() as context:
        context.prec = 1
        result = chain_twr(
            Fraction(opening), [(Fraction(value), Fraction(flow)) for value, flow in days]
        )
    assert result.twr == expected
    if expected is None:
        assert result.failures[0][1] == P.NO_CAPITAL_AT_RISK


@pytest.mark.parametrize(
    "opening,value,flow,reason",
    [
        (10, 1, -11, P.NON_POSITIVE_CAPITAL_BASE),
        (10, -1, 0, P.NEGATIVE_PERFORMANCE_VALUE),
        (0, 1, 0, P.ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE),
    ],
)
def test_capital_conditions_no_partial_return(opening, value, flow, reason):
    result = chain_twr(
        Fraction(100),
        [
            (Fraction(opening), Fraction(0)),
            (Fraction(value), Fraction(flow)),
            (Fraction(200), Fraction(200)),
        ],
    )
    assert result.twr is None
    assert reason in [failure[1] for failure in result.failures]


@pytest.mark.parametrize(
    "kind,sign,external",
    [
        (K.DEPOSIT, 1, True),
        (K.WITHDRAWAL, -1, True),
        (K.BUY, -1, False),
        (K.SELL, 1, False),
        (K.DIVIDEND, 1, False),
        (K.COUPON, 1, False),
        (K.FEE, -1, False),
        (K.TAX, -1, False),
    ],
)
def test_all_eight_cash_effects_no_double_counting(kind, sign, external):
    result = calc([fact(), fact(kind, "10", 2)], [price("0", 1)]).performance
    assert result.closing_value is not None and result.closing_value.amount == 100 + sign * 10
    assert result.twr == (Fraction(0) if external else Fraction(sign, 10))


def test_negative_cash_positive_value_mismatched_trade_cash_and_zero_price():
    history = [fact(), fact(K.BUY, "110", 2, "2")]
    positive = calc(history, [price("60", 2)]).performance
    assert positive.closing_value is not None and positive.closing_value.amount == 110
    assert positive.twr == Fraction(1, 10)
    zero = calc([fact(), fact(K.BUY, "100", 2)], [price("0", 2)]).performance
    assert zero.twr == -1 and zero.is_fully_resolved


def test_missing_price_no_future_fallback_and_no_partial_twr():
    result = calc([fact(), fact(K.BUY, "100", 2)], [price("110", 3)], end=3).performance
    assert result.twr is None and result.opening_value is not None
    assert result.closing_value is not None and result.closing_value.amount == 110
    assert result.unresolved_components[0].reason == P.MISSING_MARKET_PRICE
    assert result.unresolved_components[0].date == D(2)
    assert result.unresolved_components[0].account_id == 1
    assert result.unresolved_components[0].instrument_id == 1


def test_latest_applicable_price_and_closed_position_needs_no_price():
    history = [fact(), fact(K.BUY, "100", 2), fact(K.SELL, "120", 3)]
    result = calc(history, [price("110", 1), price("999", 4)], end=3).performance
    assert result.twr == Fraction(1, 5)
    closed = calc(history, [], start=4, end=4).performance
    assert closed.is_fully_resolved and closed.twr == 0


def test_no_basis_or_realised_dependency_negative_positions_are_signed():
    result = calc([fact(), fact(K.SELL, "20", 2)], [price("10", 1)]).performance
    assert result.twr == Fraction(1, 10)
    # USD acquisition basis is irrelevant when USD cash is exactly zero and marking is EUR.
    result = calc(
        [fact(), fact(K.BUY, "100", 1)],
        [price("100", 1, currency="EUR"), price("110", 2, currency="EUR")],
    ).performance
    assert result.currency_code == "EUR" and result.twr == Fraction(1, 10)


@pytest.mark.parametrize(
    "facts,prices",
    [
        ([fact(), fact(K.DEPOSIT, "1", 2, currency="EUR")], []),
        ([fact(), fact(K.BUY, "50", 2)], [price("50", 2, currency="EUR")]),
    ],
)
def test_multiple_economic_currencies_never_convert_or_return_per_currency(facts, prices):
    result = calc(facts, prices).performance
    assert result.twr is None and result.currency_code is None
    assert result.opening_value is None and result.closing_value is None
    assert P.MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX in [
        d.reason for d in result.unresolved_components
    ]


def test_account_first_offsets_cannot_hide_missing_price():
    result = reconstruct_performance(
        {1: [fact(K.BUY, "10", 1)], 2: [fact(K.SELL, "10", 1, account=2)]}, [], D(2), D(3)
    ).performance
    assert result.twr is None
    assert {d.account_id for d in result.unresolved_components} == {1, 2}


def test_same_day_netting_and_complete_withdrawal_preserves_prior_twr():
    history = [
        fact(),
        fact(K.DIVIDEND, "10", 2),
        fact(K.WITHDRAWAL, "120", 3),
        fact(K.DEPOSIT, "10", 3),
    ]
    result = calc(history, end=3).performance
    assert result.twr == Fraction(1, 10)
    assert result.closing_value is not None and result.closing_value.amount == 0


@pytest.mark.parametrize(
    "history,quotes,start,end,reason",
    [
        ([fact()], [], 2, 2, B.MISSING_BENCHMARK_MARKET_PRICE),
        ([fact()], [price("0", 1, 2)], 2, 2, B.ZERO_BENCHMARK_OPENING_PRICE),
        ([fact(day=2)], [price("10", 2, 2)], 2, 2, B.MISSING_BENCHMARK_MARKET_PRICE),
        (
            [fact(day=2)],
            [price("0", 1, 2), price("10", 2, 2)],
            2,
            2,
            B.ZERO_BENCHMARK_FLOW_EXECUTION_PRICE,
        ),
        ([fact()], [price("10", 1, 2, "EUR")], 2, 2, B.BENCHMARK_CURRENCY_MISMATCH),
        (
            [fact(), fact(K.WITHDRAWAL, "90", 3)],
            [price("10", 1, 2), price("5", 2, 2)],
            2,
            3,
            B.BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE,
        ),
        ([fact(), fact(K.BUY, "100", 2)], [], 2, 2, B.UNRESOLVED_PORTFOLIO_PERFORMANCE),
        (
            [fact()],
            [price("10", 1, 2), price("0", 2, 2), price("10", 3, 2)],
            2,
            3,
            B.ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE,
        ),
    ],
)
def test_seven_benchmark_reasons_and_missing_previous_date(history, quotes, start, end, reason):
    result = calc(history, quotes, start, end, 2)
    assert result.benchmark is not None
    benchmark = result.benchmark
    assert benchmark.benchmark_twr is None and benchmark.active_return is None
    assert benchmark.ending_value_difference is None and not benchmark.is_fully_resolved
    assert benchmark.unresolved_components[0].reason == reason
    if reason == B.ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE:
        assert result.performance.twr == 0
        diagnostic = benchmark.unresolved_components[0]
        assert diagnostic.date == D(3)
        assert diagnostic.capital_base is not None and diagnostic.capital_base.amount == 0
        assert diagnostic.value is not None and diagnostic.value.amount == 100


def test_exact_fractional_benchmark_units_previous_price_net_flow_and_comparison():
    # Initial 100/3 units; next-date net deposit 2 executes at 3, not closing price 7.
    history = [fact(), fact(K.DEPOSIT, "3", 2), fact(K.WITHDRAWAL, "1", 2)]
    result = calc(history, [price("3", 1, 2), price("7", 2, 2), price("99", 3, 2)], benchmark=2)
    b = result.benchmark
    assert b is not None and b.is_fully_resolved
    assert b.ending_value is not None and b.ending_value.amount == 238
    assert b.benchmark_twr == Fraction(4, 3)
    assert b.active_return == Fraction(-4, 3)
    assert b.ending_value_difference is not None and b.ending_value_difference.amount == -136


def test_zero_opening_no_purchase_and_zero_valuation_without_flow():
    result = calc([fact(day=2)], [price("3", 1, 2), price("0", 2, 2)], benchmark=2).benchmark
    assert result is not None and result.benchmark_twr == -1
    assert result.ending_value is not None and result.ending_value.amount == 0


def test_benchmark_withdrawal_to_zero_neutral_no_price_required_for_zero_units():
    result = calc(
        [fact(), fact(K.WITHDRAWAL, "100", 3)], [price("10", 1, 2)], end=3, benchmark=2
    ).benchmark
    assert result is not None and result.is_fully_resolved and result.benchmark_twr == 0


def test_recomputation_backdated_facts_and_prices():
    history = [fact(), fact(K.BUY, "100", 2)]
    quotes = [price("100", 1), price("110", 3)]
    assert calc(history, quotes, end=3).performance.twr == Fraction(1, 10)
    assert calc(history + [fact(K.FEE, "1", 2)], quotes, end=3).performance.twr == Fraction(9, 100)
    assert calc(history, [price("100", 1), price("120", 3)], end=3).performance.twr == Fraction(
        1, 5
    )


def test_low_decimal_context_and_invalid_duplicate_facts():
    with localcontext() as context:
        context.prec = 1
        result = calc(
            [fact(), fact(K.BUY, "100", 2, "0.123456789012")], [price("333.123456789012", 2)]
        ).performance
        assert result.closing_value is not None
        assert result.closing_value.amount == Fraction(123456789012 * 333123456789012, 10**24)
    with pytest.raises(ValueError, match="Duplicate"):
        calc([], [price("1", 1), price("2", 1)])
    with pytest.raises(ValueError, match="opening"):
        reconstruct_performance({}, [], date.min, D(2))
