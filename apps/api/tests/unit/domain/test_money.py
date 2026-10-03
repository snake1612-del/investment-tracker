from dataclasses import replace
from datetime import date
from decimal import Decimal, Inexact, Rounded, localcontext

import pytest

from app.domain.portfolio.engine.money import (
    InvalidMoneyHistory,
    aggregate_money_summaries,
    reconstruct_money_summary,
)
from app.domain.transactions import CanonicalTransaction as Transaction
from app.domain.transactions import InvalidTransaction, TransactionType

DAY = date(2020, 1, 1)


def event(kind: TransactionType, amount: str = "1", currency: str = "USD") -> Transaction:
    value = Decimal(amount)
    if kind in {TransactionType.BUY, TransactionType.SELL}:
        constructor = Transaction.buy if kind is TransactionType.BUY else Transaction.sell
        return constructor(1, 2, Decimal("3"), Decimal("7"), value, currency, DAY)
    if kind in {TransactionType.DIVIDEND, TransactionType.COUPON}:
        constructor = (
            Transaction.dividend if kind is TransactionType.DIVIDEND else Transaction.coupon
        )
        return constructor(1, 2, value, currency, DAY)
    return getattr(Transaction, kind.value.lower())(1, value, currency, DAY)


@pytest.mark.parametrize("kind", list(TransactionType)[1:2] + list(TransactionType)[4:])
@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity", "1E-9", "10000000000000000"])
def test_new_constructors_reject_invalid_cash(kind: TransactionType, amount: str) -> None:
    with pytest.raises(InvalidTransaction):
        event(kind, amount)


@pytest.mark.parametrize(
    "kind",
    [
        TransactionType.WITHDRAWAL,
        TransactionType.DIVIDEND,
        TransactionType.COUPON,
        TransactionType.FEE,
        TransactionType.TAX,
    ],
)
@pytest.mark.parametrize("currency", ["usd", "US", "USDD", "US1", "ÜSD"])
def test_new_constructors_reject_invalid_currency(kind: TransactionType, currency: str) -> None:
    with pytest.raises(InvalidTransaction):
        event(kind, currency=currency)


@pytest.mark.parametrize("kind", list(TransactionType))
def test_explicit_eight_cash_effects(kind: TransactionType) -> None:
    (summary,) = reconstruct_money_summary([event(kind, "1E-8")], DAY)
    sign = (
        1
        if kind
        in {
            TransactionType.DEPOSIT,
            TransactionType.SELL,
            TransactionType.DIVIDEND,
            TransactionType.COUPON,
        }
        else -1
    )
    assert summary.cash_balance == Decimal("0.00000001") * sign
    assert summary.currency_code == "USD"


def test_categories_cutoff_settlement_and_active_zero() -> None:
    facts = [event(kind) for kind in TransactionType]
    facts.append(replace(event(TransactionType.DEPOSIT, "100"), effective_date=date(2021, 1, 1)))
    facts[2] = replace(facts[2], settlement_date=date(2030, 1, 1))
    (summary,) = reconstruct_money_summary(facts, DAY)
    assert summary.cash_balance == 0
    for field in (
        "deposits",
        "withdrawals",
        "buy_trade_cash_outflow",
        "sell_trade_cash_inflow",
        "gross_dividend_income",
        "gross_coupon_income",
        "fees_paid",
        "taxes_paid_or_withheld",
    ):
        assert getattr(summary, field) == 1
    assert summary.gross_investment_income == 2
    assert reconstruct_money_summary(facts, date(2019, 12, 31)) == ()
    assert reconstruct_money_summary([], DAY) == ()


def test_unbounded_totals_are_context_independent_and_partitioned() -> None:
    maximum = "9999999999999999.99999999"
    facts = [event(TransactionType.DEPOSIT, maximum)] * 4
    facts += [event(TransactionType.TAX, "1E-8", "EUR")]
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        summaries = reconstruct_money_summary(facts, DAY)
        combined = aggregate_money_summaries([summaries, summaries])
    assert [item.currency_code for item in summaries] == ["EUR", "USD"]
    assert summaries[0].cash_balance == Decimal("-1E-8")
    assert summaries[1].cash_balance == Decimal("39999999999999999.99999996")
    assert combined[1].deposits == Decimal("79999999999999999.99999992")


@pytest.mark.parametrize(
    "changes",
    [
        {"cash_amount": Decimal("0")},
        {"cash_amount": Decimal("NaN")},
        {"cash_amount": Decimal("1E-9")},
        {"cash_amount": Decimal("1E16")},
        {"cash_amount": 1.0},
        {"currency_code": "usd"},
        {"type": "FUTURE"},
        {"quantity": Decimal("1")},
        {"instrument_id": 2},
        {"settlement_date": DAY},
        {"effective_date": None},
    ],
)
def test_malformed_history_is_internal_failure(changes: dict) -> None:
    with pytest.raises(InvalidMoneyHistory):
        reconstruct_money_summary([replace(event(TransactionType.DEPOSIT), **changes)], DAY)


@pytest.mark.parametrize("kind", [TransactionType.DIVIDEND, TransactionType.COUPON])
def test_income_requires_instrument(kind: TransactionType) -> None:
    constructor = Transaction.dividend if kind is TransactionType.DIVIDEND else Transaction.coupon
    with pytest.raises(InvalidTransaction):
        constructor(1, 0, Decimal("1"), "USD", DAY)
