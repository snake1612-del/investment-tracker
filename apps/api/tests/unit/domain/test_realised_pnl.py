from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Context, Decimal, localcontext
from fractions import Fraction

import pytest

from app.domain.portfolio.engine import fifo as fifo_module
from app.domain.portfolio.engine.fifo import (
    ExactMoney,
    FifoReconstruction,
    LotTransactionFact,
    reconstruct_fifo_lots,
)
from app.domain.portfolio.engine.realised_pnl import (
    GrossRealisedPnlError,
    RealisedPnlUnresolvedReason,
    aggregate_portfolio_gross_realised_pnl,
    reconstruct_gross_realised_pnl,
    summarize_account_gross_realised_pnl,
)
from app.domain.transactions import TransactionType


def facts() -> tuple[LotTransactionFact, ...]:
    return (
        LotTransactionFact(
            1, 1, TransactionType.BUY, 1, Decimal("3"), Decimal("100"), "USD", date(2020, 1, 1)
        ),
        LotTransactionFact(
            2, 1, TransactionType.SELL, 1, Decimal("1"), Decimal("100"), "USD", date(2020, 1, 2)
        ),
    )


def test_exact_money_subtraction_currency_safety() -> None:
    assert ExactMoney(Fraction(100), "USD") - ExactMoney(Fraction(80), "USD") == ExactMoney(
        Fraction(20), "USD"
    )
    with pytest.raises(ValueError, match="different currencies"):
        _ = ExactMoney(Fraction(100), "USD") - ExactMoney(Fraction(80), "RUB")


def test_duplicate_facts_and_missing_sell_fail() -> None:
    history = facts()
    fifo = reconstruct_fifo_lots(history)
    with pytest.raises(GrossRealisedPnlError, match="Duplicate"):
        reconstruct_gross_realised_pnl(fifo, (*history, history[0]))
    with pytest.raises(GrossRealisedPnlError, match="SELL fact"):
        reconstruct_gross_realised_pnl(fifo, history[:1])


@pytest.mark.parametrize(
    "changes",
    [
        {"type": TransactionType.BUY},
        {"account_id": 2},
        {"instrument_id": 2},
        {"quantity": Decimal("1E-13")},
        {"quantity": None},
        {"quantity": Decimal("0")},
        {"cash_amount": Decimal("1E-9")},
        {"cash_amount": None},
        {"cash_amount": Decimal("NaN")},
        {"cash_amount": Decimal("-1")},
        {"currency_code": None},
        {"currency_code": "usd"},
        {"effective_date": None},
    ],
)
def test_malformed_or_inconsistent_referenced_sell_fails(changes: dict[str, object]) -> None:
    history = facts()
    fifo = reconstruct_fifo_lots(history)
    with pytest.raises(GrossRealisedPnlError):
        reconstruct_gross_realised_pnl(fifo, (history[0], replace(history[1], **changes)))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "quantity", [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("1E-13"), Decimal("2")]
)
def test_malformed_components_or_quantity_conservation_violation_fail(quantity: Decimal) -> None:
    history = facts()
    fifo = reconstruct_fifo_lots(history)
    corrupted = replace(
        fifo, disposal_matches=(replace(fifo.disposal_matches[0], matched_quantity=quantity),)
    )
    with pytest.raises(GrossRealisedPnlError):
        reconstruct_gross_realised_pnl(corrupted, history)


def test_component_instrument_and_duplicate_unmatched_remainders_fail() -> None:
    history = (replace(facts()[1], quantity=Decimal("4")),)
    fifo = reconstruct_fifo_lots(history)
    duplicate = replace(fifo, unmatched_sells=(*fifo.unmatched_sells, *fifo.unmatched_sells))
    with pytest.raises(GrossRealisedPnlError, match="Multiple unmatched"):
        reconstruct_gross_realised_pnl(duplicate, history)
    corrupted = replace(fifo, unmatched_sells=(replace(fifo.unmatched_sells[0], instrument_id=2),))
    with pytest.raises(GrossRealisedPnlError, match="Instrument"):
        reconstruct_gross_realised_pnl(corrupted, history)
    mismatched_quantity = replace(
        fifo, unmatched_sells=(replace(fifo.unmatched_sells[0], unmatched_quantity=Decimal("3")),)
    )
    with pytest.raises(GrossRealisedPnlError, match="quantity conservation"):
        reconstruct_gross_realised_pnl(mismatched_quantity, history)


def test_authoritative_matches_used_without_fifo_rerun_or_lot_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = facts()
    fifo = reconstruct_fifo_lots(history)

    def forbidden(*args: object, **kwargs: object) -> FifoReconstruction:
        raise AssertionError("F005 must not rerun FIFO")

    monkeypatch.setattr(fifo_module, "reconstruct_fifo_lots", forbidden)
    result = reconstruct_gross_realised_pnl(replace(fifo, lots=()), history)
    match = result.sells[0].matches[0]
    assert match.removed_basis == fifo.disposal_matches[0].removed_basis
    assert match.realised_pnl == ExactMoney(Fraction(200, 3), "USD")
    assert result.sells[0].effective_date == history[1].effective_date
    with pytest.raises(FrozenInstanceError):
        match.instrument_id = 7  # type: ignore[misc]


def test_proceeds_conservation_guard_rejects_bad_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = facts()
    fifo = reconstruct_fifo_lots(history)

    def bad_allocation(self: ExactMoney, units: int, original_units: int) -> ExactMoney:
        return ExactMoney(Fraction(1), self.currency_code)

    monkeypatch.setattr(ExactMoney, "allocated", bad_allocation)
    with pytest.raises(GrossRealisedPnlError, match="proceeds conservation"):
        reconstruct_gross_realised_pnl(fifo, history)


def test_fully_resolved_pnl_conservation_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    history = facts()
    fifo = reconstruct_fifo_lots(history)
    original = ExactMoney.__sub__

    def bad_subtraction(self: ExactMoney, other: ExactMoney) -> ExactMoney:
        return original(self, other) + ExactMoney(Fraction(1), self.currency_code)

    # Two matched components: an erroneous +1 per subtraction does not conserve
    # the aggregate SELL subtraction, so the explicit invariant must catch it.
    history = (
        replace(history[0], quantity=Decimal("0.5")),
        replace(history[0], transaction_id=3, quantity=Decimal("0.5")),
        history[1],
    )
    fifo = reconstruct_fifo_lots(history)
    monkeypatch.setattr(ExactMoney, "__sub__", bad_subtraction)
    with pytest.raises(GrossRealisedPnlError, match="P&L conservation"):
        reconstruct_gross_realised_pnl(fifo, history)


def test_unmatched_has_no_synthetic_basis_or_pnl_and_summary_is_immutable() -> None:
    history = (facts()[1],)
    result = reconstruct_gross_realised_pnl(reconstruct_fifo_lots(history), history)
    component = result.sells[0].unmatched_proceeds
    assert component is not None
    assert component.unresolved_reason is RealisedPnlUnresolvedReason.MISSING_ACQUISITION_BASIS
    assert not hasattr(component, "removed_basis")
    assert not hasattr(component, "realised_pnl")
    summary = summarize_account_gross_realised_pnl(result)
    assert summary.resolved_pnl_by_currency == {}
    assert not summary.is_fully_resolved
    with pytest.raises(TypeError):
        summary.resolved_pnl_by_currency["USD"] = ExactMoney(Fraction(1), "USD")  # type: ignore[index]


def test_tiny_decimal_context_exact_cash_allocation_subtraction_and_aggregation() -> None:
    history = (
        replace(facts()[0], quantity=Decimal("1.000000000001"), cash_amount=Decimal("10.12345678")),
        replace(
            facts()[0],
            transaction_id=3,
            quantity=Decimal("2.000000000002"),
            cash_amount=Decimal("20.24691356"),
        ),
        replace(
            facts()[1], quantity=Decimal("3.000000000003"), cash_amount=Decimal("100.12345678")
        ),
    )
    with localcontext(Context(prec=3)):
        fifo = reconstruct_fifo_lots(history)
        result = reconstruct_gross_realised_pnl(fifo, history)
        assert result.sells[0].matches[0].allocated_proceeds.amount == Fraction(
            10012345678, 300000000
        )
        summary = summarize_account_gross_realised_pnl(result)
        assert summary.resolved_pnl_by_currency["USD"].amount == Fraction(6975308644, 100000000)
        portfolio = aggregate_portfolio_gross_realised_pnl(
            [summary, replace(summary, account_id=2)]
        )
        assert portfolio.resolved_pnl_by_currency["USD"].amount == Fraction(13950617288, 100000000)
        assert portfolio.is_fully_resolved


def test_no_disposals_empty_and_buy_only_results() -> None:
    assert (
        reconstruct_gross_realised_pnl(reconstruct_fifo_lots([], account_id=7), ()).account_id == 7
    )
    history = facts()[:1]
    result = reconstruct_gross_realised_pnl(reconstruct_fifo_lots(history), history)
    assert result.sells == ()
    assert summarize_account_gross_realised_pnl(result).is_fully_resolved
    assert aggregate_portfolio_gross_realised_pnl([]).is_fully_resolved
