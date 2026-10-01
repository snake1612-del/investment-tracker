"""Approved F005 reference cases with exact rational monetary expectations."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from fractions import Fraction

import pytest

from app.domain.portfolio.engine.fifo import ExactMoney, LotTransactionFact, reconstruct_fifo_lots
from app.domain.portfolio.engine.realised_pnl import (
    RealisedPnlUnresolvedReason,
    aggregate_portfolio_gross_realised_pnl,
    reconstruct_gross_realised_pnl,
    summarize_account_gross_realised_pnl,
)
from app.domain.transactions import TransactionType

MISSING = RealisedPnlUnresolvedReason.MISSING_ACQUISITION_BASIS
FX = RealisedPnlUnresolvedReason.CURRENCY_MISMATCH


def buy(
    id_: int, quantity: str, cash: str, currency: str = "USD", day: int = 1
) -> LotTransactionFact:
    return LotTransactionFact(
        id_,
        1,
        TransactionType.BUY,
        1,
        Decimal(quantity),
        Decimal(cash),
        currency,
        date(2020, 1, day),
    )


def sell(
    id_: int, quantity: str, cash: str, currency: str = "USD", day: int = 2
) -> LotTransactionFact:
    return replace(buy(id_, quantity, cash, currency, day), type=TransactionType.SELL)


@pytest.mark.parametrize(
    ("facts", "expected_pnl", "expected_allocated", "expected_reasons"),
    [
        pytest.param(
            [buy(1, "5", "50"), sell(2, "5", "75")],
            [Fraction(25)],
            [Fraction(75)],
            [],
            id="simple-profit",
        ),
        pytest.param(
            [buy(1, "5", "50"), sell(2, "5", "25")],
            [Fraction(-25)],
            [Fraction(25)],
            [],
            id="simple-loss",
        ),
        pytest.param(
            [buy(1, "5", "50"), sell(2, "5", "50")],
            [Fraction(0)],
            [Fraction(50)],
            [],
            id="exact-zero",
        ),
        pytest.param(
            [buy(1, "2", "20"), buy(2, "3", "60"), sell(3, "4", "100")],
            [Fraction(30), Fraction(10)],
            [Fraction(50), Fraction(50)],
            [],
            id="sell-across-fifo-lots",
        ),
        pytest.param(
            [buy(1, "1", "10"), buy(2, "2", "20"), sell(3, "3", "100")],
            [Fraction(70, 3), Fraction(140, 3)],
            [Fraction(100, 3), Fraction(200, 3)],
            [],
            id="repeating-proceeds-100-over-3",
        ),
        pytest.param(
            [buy(1, "3", "100"), sell(2, "1", "100")],
            [Fraction(200, 3)],
            [Fraction(100)],
            [],
            id="repeating-basis",
        ),
        pytest.param(
            [
                buy(1, "3", "100"),
                buy(2, "2", "20"),
                sell(3, "3", "100", day=3),
                sell(4, "1", "100", day=2),
            ],
            [Fraction(200, 3), Fraction(0), Fraction(70, 3)],
            [Fraction(100), Fraction(200, 3), Fraction(100, 3)],
            [],
            id="repeating-basis-and-proceeds",
        ),
        pytest.param(
            [buy(1, "5", "50"), sell(2, "5", "60")],
            [Fraction(10)],
            [Fraction(60)],
            [],
            id="factual-cash-not-quantity-times-price",
        ),
        pytest.param(
            [buy(1, "5", "50"), sell(2, "8", "80")],
            [Fraction(0)],
            [Fraction(50), Fraction(30)],
            [MISSING],
            id="oversell-partially-resolved",
        ),
        pytest.param([sell(1, "4", "80")], [], [Fraction(80)], [MISSING], id="sell-only"),
        pytest.param(
            [buy(1, "5", "50", "RUB"), sell(2, "5", "75")],
            [None],
            [Fraction(75)],
            [FX],
            id="currency-mismatch",
        ),
        pytest.param(
            [buy(1, "2", "20"), buy(2, "2", "200", "RUB"), sell(3, "4", "100")],
            [Fraction(30), None],
            [Fraction(50), Fraction(50)],
            [FX],
            id="mixed-basis-currencies",
        ),
        pytest.param(
            [buy(1, "2", "20"), buy(2, "2", "200", "RUB"), sell(3, "6", "150")],
            [Fraction(30), None],
            [Fraction(50), Fraction(50), Fraction(50)],
            [FX, MISSING],
            id="resolved-fx-and-missing-basis-simultaneously",
        ),
    ],
)
def test_normative_results(
    facts: list[LotTransactionFact],
    expected_pnl: list[Fraction | None],
    expected_allocated: list[Fraction],
    expected_reasons: list[RealisedPnlUnresolvedReason],
) -> None:
    fifo = reconstruct_fifo_lots(facts)
    result = reconstruct_gross_realised_pnl(fifo, facts)
    assert [
        match.realised_pnl.amount if match.realised_pnl is not None else None
        for item in result.sells
        for match in item.matches
    ] == expected_pnl
    assert [
        component.allocated_proceeds.amount
        for item in result.sells
        for component in (
            *item.matches,
            *((item.unmatched_proceeds,) if item.unmatched_proceeds is not None else ()),
        )
    ] == expected_allocated
    assert [
        component.unresolved_reason
        for item in result.sells
        for component in item.unresolved_components
    ] == expected_reasons
    for item in result.sells:
        allocated = sum((match.allocated_proceeds.amount for match in item.matches), Fraction(0))
        if item.unmatched_proceeds is not None:
            allocated += item.unmatched_proceeds.allocated_proceeds.amount
        assert allocated == item.total_proceeds.amount
        assert item.is_fully_resolved == (not item.unresolved_components)
        if item.is_fully_resolved:
            pnl = sum(
                (
                    match.realised_pnl.amount
                    for match in item.matches
                    if match.realised_pnl is not None
                ),
                Fraction(0),
            )
            assert pnl == item.total_proceeds.amount - sum(
                (match.removed_basis.amount for match in item.matches), Fraction(0)
            )


@pytest.mark.parametrize("type_", [TransactionType.FEE, TransactionType.TAX])
def test_fee_and_tax_excluded(type_: TransactionType) -> None:
    facts = [buy(1, "5", "50"), sell(2, "5", "75")]
    baseline = reconstruct_gross_realised_pnl(reconstruct_fifo_lots(facts), facts)
    # Relationships are excluded from LotTransactionFact: linked and unlinked
    # charges reach F004 as explicit no-lot-effect events, never F005 adjustments.
    charged = facts + [replace(buy(3, "1", "1000", "RUB"), type=type_)]
    assert reconstruct_gross_realised_pnl(reconstruct_fifo_lots(charged), charged) == baseline


def test_account_isolation_and_portfolio_currency_partitioning() -> None:
    histories = [
        [buy(1, "5", "50"), sell(2, "5", "75")],
        [replace(sell(3, "4", "80"), account_id=2)],
        [
            replace(buy(4, "2", "20", "RUB"), account_id=3),
            replace(sell(5, "2", "60", "RUB"), account_id=3),
        ],
    ]
    summaries = [
        summarize_account_gross_realised_pnl(
            reconstruct_gross_realised_pnl(reconstruct_fifo_lots(facts), facts)
        )
        for facts in histories
    ]
    result = aggregate_portfolio_gross_realised_pnl(summaries)
    assert result.resolved_pnl_by_currency == {
        "USD": ExactMoney(Fraction(25), "USD"),
        "RUB": ExactMoney(Fraction(40), "RUB"),
    }
    assert not result.is_fully_resolved
    assert result.unresolved_components[0].account_id == 2
    assert result.unresolved_components[0].component.source_sell_transaction_id == 3
    assert result.unresolved_components[0].component.unresolved_reason is MISSING


def test_backdated_buy_changes_authoritative_basis_and_pnl() -> None:
    initial = [buy(1, "5", "50", day=2), sell(2, "5", "100", day=3)]
    before = reconstruct_gross_realised_pnl(reconstruct_fifo_lots(initial), initial)
    backdated = initial + [buy(3, "5", "25", day=1)]
    after = reconstruct_gross_realised_pnl(reconstruct_fifo_lots(backdated), backdated)
    assert before.sells[0].matches[0].realised_pnl == ExactMoney(Fraction(50), "USD")
    assert after.sells[0].matches[0].source_buy_transaction_id == 3
    assert after.sells[0].matches[0].realised_pnl == ExactMoney(Fraction(75), "USD")


def test_backdated_sell_changes_matching_and_realisation_date() -> None:
    initial = [buy(1, "5", "50", day=2), sell(2, "5", "100", day=3)]
    moved = [initial[0], replace(initial[1], effective_date=date(2020, 1, 1))]
    result = reconstruct_gross_realised_pnl(reconstruct_fifo_lots(moved), moved)
    assert result.sells[0].effective_date == date(2020, 1, 1)
    assert result.sells[0].matches == ()
    assert result.sells[0].unmatched_proceeds is not None
    assert result.sells[0].unmatched_proceeds.allocated_proceeds == ExactMoney(Fraction(100), "USD")
