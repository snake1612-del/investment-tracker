from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.fifo import LotTransactionFact
from app.domain.portfolio.engine.valuation import (
    ValuationReason,
    aggregate_valuations,
    reconstruct_account_valuation,
    select_prices,
)
from app.domain.transactions import CanonicalTransaction, TransactionType

DAY = date(2020, 1, 2)


def trade(
    id_: int,
    kind: TransactionType,
    quantity: str,
    cash: str = "10",
    currency: str = "USD",
    day: date = DAY,
    account: int = 1,
    instrument: int = 1,
) -> tuple[CanonicalTransaction, LotTransactionFact]:
    constructor = (
        CanonicalTransaction.buy if kind is TransactionType.BUY else CanonicalTransaction.sell
    )
    tx = constructor(
        account, instrument, Decimal(quantity), Decimal("999"), Decimal(cash), currency, day
    )
    return tx, LotTransactionFact(
        id_, account, kind, instrument, tx.quantity, tx.cash_amount, currency, day
    )


def valuation(
    trades: list[tuple[CanonicalTransaction, LotTransactionFact]],
    prices: list[MarketPrice] | None = None,
    account: int = 1,
):
    return reconstruct_account_valuation(
        account, (item[0] for item in trades), (item[1] for item in trades), prices or [], DAY
    )


def price(value: str = "20", currency: str = "USD", day: date = DAY, instrument: int = 1):
    return MarketPrice(instrument, Decimal(value), currency, day)


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "1E-13", "10000000000000000"])
def test_invalid_prices(value: str):
    with pytest.raises(ValueError):
        price(value)


@pytest.mark.parametrize(
    "value", ["0", "-0", "0E+999999", "1E-12", "9999999999999999.999999999999"]
)
def test_exact_price_boundaries(value: str):
    assert price(value).price == Decimal(value)


def test_latest_applicable_selection_not_insertion_order():
    previous = price("10", day=date(2020, 1, 1))
    current = price()
    future = price("99", day=date(2020, 1, 3))
    assert select_prices([future, current, previous], DAY)[1] == current
    with pytest.raises(ValueError):
        select_prices([current, current], DAY)


@pytest.mark.parametrize("prices", [[], [price(day=date(2020, 1, 3))]])
def test_missing_price_never_uses_trade_facts(prices: list[MarketPrice]):
    item = valuation([trade(1, TransactionType.BUY, "1")], prices).instruments[0]
    assert item.selected_market_price is None and item.market_value is None
    assert [x.reason for x in item.unresolved_components] == [ValuationReason.MISSING_MARKET_PRICE]


def test_zero_requires_no_price_and_future_trades_excluded():
    assert (
        valuation(
            [trade(1, TransactionType.BUY, "1"), trade(2, TransactionType.SELL, "1")]
        ).instruments
        == ()
    )
    assert valuation([trade(1, TransactionType.BUY, "1", day=date(2020, 1, 3))]).is_fully_resolved


@pytest.mark.parametrize("mark,expected", [("20", Fraction(20)), ("0", Fraction(-20))])
def test_long_partial_sell_uses_remaining_cash_basis(mark: str, expected: Fraction):
    result = valuation(
        [trade(1, TransactionType.BUY, "3", "30"), trade(2, TransactionType.SELL, "1")],
        [price(mark)],
    )
    assert result.is_fully_resolved
    assert result.resolved_unrealised_pnl_by_currency[0].amount == expected
    expected_value = Fraction(2) * Fraction(Decimal(mark))
    assert result.resolved_market_value_by_currency[0].amount == expected_value


def test_negative_with_and_without_price_has_independent_limitations():
    facts = [trade(1, TransactionType.SELL, "2")]
    item = valuation(facts, [price()]).instruments[0]
    assert item.market_value is not None and item.market_value.amount == -40
    assert item.unresolved_components[0].reason is ValuationReason.UNSUPPORTED_NEGATIVE_POSITION
    missing = valuation(facts).instruments[0]
    assert {x.reason for x in missing.unresolved_components} == {
        ValuationReason.MISSING_MARKET_PRICE,
        ValuationReason.UNSUPPORTED_NEGATIVE_POSITION,
    }


def test_unmatched_sell_later_buy_cannot_invent_net_basis():
    facts = [trade(1, TransactionType.SELL, "1"), trade(2, TransactionType.BUY, "3")]
    item = valuation(facts, [price()]).instruments[0]
    assert item.market_value is not None and item.market_value.amount == 40
    assert not item.resolved_unrealised_pnl_by_currency
    assert item.unresolved_components[0].reason is ValuationReason.MISSING_ACQUISITION_BASIS
    assert item.unresolved_components[0].market_value_component == item.market_value


def test_mixed_basis_partial_resolution_preserves_exact_legs():
    result = valuation(
        [trade(1, TransactionType.BUY, "1"), trade(2, TransactionType.BUY, "2", "7", "EUR")],
        [price()],
    )
    assert not result.is_fully_resolved
    assert result.resolved_unrealised_pnl_by_currency[0].amount == 10
    mismatch = result.instruments[0].unresolved_components[0]
    assert mismatch.reason is ValuationReason.CURRENCY_MISMATCH
    assert (
        mismatch.market_value_component is not None and mismatch.market_value_component.amount == 40
    )
    assert mismatch.remaining_basis is not None and mismatch.remaining_basis.currency_code == "EUR"


def test_context_independent_rational_remaining_basis_and_product():
    with localcontext() as context:
        context.prec = 2
        result = valuation(
            [trade(1, TransactionType.BUY, "3", "1"), trade(2, TransactionType.SELL, "1")],
            [price("0.123456789012")],
        )
    assert result.resolved_unrealised_pnl_by_currency[0].amount == Fraction(
        246913578024, 10**12
    ) - Fraction(2, 3)


def test_account_first_portfolio_preserves_offsetting_unresolved_positions():
    long = valuation([trade(1, TransactionType.BUY, "1")], [price()])
    short = valuation([trade(2, TransactionType.SELL, "1", account=2)], [price()], account=2)
    result = aggregate_valuations([long, short])
    assert not result.is_fully_resolved
    assert len(result.instruments) == 2
    assert result.resolved_market_value_by_currency[0].amount == 0
    assert result.resolved_unrealised_pnl_by_currency[0].amount == 10
    assert result.instruments[1].unresolved_components[0].account_id == 2


def test_same_currency_aggregation_and_no_cross_currency_total():
    facts = [
        trade(1, TransactionType.BUY, "1"),
        trade(2, TransactionType.BUY, "2", "3", "EUR", instrument=2),
        trade(3, TransactionType.BUY, "1", instrument=3),
    ]
    result = valuation(facts, [price(), price("5", "EUR", instrument=2), price("2", instrument=3)])
    assert [(x.currency_code, x.amount) for x in result.resolved_market_value_by_currency] == [
        ("EUR", 10),
        ("USD", 22),
    ]
