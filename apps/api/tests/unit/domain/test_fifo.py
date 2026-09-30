from dataclasses import FrozenInstanceError, fields, replace
from datetime import date
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from typing import cast

import pytest

from app.domain.portfolio.engine.exact import decimal_to_scaled_int, scaled_int_to_decimal
from app.domain.portfolio.engine.fifo import (
    ExactMoney,
    FifoReconstructionError,
    LotTransactionFact,
    aggregate_portfolio_summaries,
    reconstruct_fifo_lots,
    summarize_account,
)
from app.domain.transactions import TransactionType


def fact(id_: int = 1, type_: TransactionType = TransactionType.BUY) -> LotTransactionFact:
    return LotTransactionFact(
        id_, 1, type_, 1, Decimal("3"), Decimal("100"), "USD", date(2020, 1, 1)
    )


def test_dedicated_immutable_input_fields() -> None:
    assert {field.name for field in fields(LotTransactionFact)} == {
        "transaction_id",
        "account_id",
        "type",
        "instrument_id",
        "quantity",
        "cash_amount",
        "currency_code",
        "effective_date",
    }
    with pytest.raises(FrozenInstanceError):
        fact().transaction_id = 2  # type: ignore[misc]


@pytest.mark.parametrize("type_", [TransactionType.BUY, TransactionType.SELL])
@pytest.mark.parametrize(
    "changes",
    [
        {"transaction_id": None},
        {"transaction_id": 0},
        {"account_id": None},
        {"instrument_id": None},
        {"quantity": None},
        {"quantity": Decimal("-1")},
        {"quantity": Decimal("0")},
        {"quantity": Decimal("NaN")},
        {"quantity": Decimal("Infinity")},
        {"quantity": Decimal("1E-13")},
        {"effective_date": None},
        {"effective_date": "2020-01-01"},
    ],
)
def test_malformed_required_trade_facts_fail(
    type_: TransactionType, changes: dict[str, object]
) -> None:
    with pytest.raises(FifoReconstructionError):
        reconstruct_fifo_lots([replace(fact(type_=type_), **changes)])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"cash_amount": None},
        {"cash_amount": Decimal("NaN")},
        {"cash_amount": Decimal("-1")},
        {"cash_amount": Decimal("1E-9")},
        {"currency_code": None},
        {"currency_code": "usd"},
        {"currency_code": 17},
    ],
)
def test_malformed_buy_basis_fails(changes: dict[str, object]) -> None:
    with pytest.raises(FifoReconstructionError):
        reconstruct_fifo_lots([replace(fact(), **changes)])  # type: ignore[arg-type]


def test_sell_basis_fields_are_not_required_or_validated() -> None:
    sell = replace(fact(2, TransactionType.SELL), cash_amount=Decimal("NaN"), currency_code=None)
    assert reconstruct_fifo_lots([fact(), sell]).lots[0].remaining_basis.amount == 0


def test_currency_safe_addition_and_immutable_summary_partition() -> None:
    assert ExactMoney(Fraction(100), "USD") + ExactMoney(Fraction(50), "USD") == ExactMoney(
        Fraction(150), "USD"
    )
    with pytest.raises(ValueError, match="different currencies"):
        _ = ExactMoney(Fraction(100), "USD") + ExactMoney(Fraction(50), "RUB")
    summary = summarize_account(reconstruct_fifo_lots([fact()]))[0]
    with pytest.raises(TypeError):
        summary.remaining_basis_by_currency["RUB"] = ExactMoney(Fraction(1), "RUB")  # type: ignore[index]


@pytest.mark.parametrize(
    "type_",
    [
        TransactionType.DEPOSIT,
        TransactionType.WITHDRAWAL,
        TransactionType.DIVIDEND,
        TransactionType.COUPON,
        TransactionType.FEE,
        TransactionType.TAX,
    ],
)
def test_explicit_no_lot_effect(type_: TransactionType) -> None:
    result = reconstruct_fifo_lots([replace(fact(type_=type_), quantity=None, cash_amount=None)])
    assert result.lots == result.disposal_matches == result.unmatched_sells == ()
    assert result.account_id == 1


def test_enum_expansion_requires_methodology_update() -> None:
    assert set(TransactionType) == {
        TransactionType.BUY,
        TransactionType.SELL,
        TransactionType.DEPOSIT,
        TransactionType.WITHDRAWAL,
        TransactionType.DIVIDEND,
        TransactionType.COUPON,
        TransactionType.FEE,
        TransactionType.TAX,
    }
    with pytest.raises(FifoReconstructionError, match="Unknown"):
        reconstruct_fifo_lots([replace(fact(), type=cast(TransactionType, "SPLIT"))])


def test_account_contamination_duplicate_id_and_wrong_boundary_fail() -> None:
    with pytest.raises(FifoReconstructionError, match="Multiple Account"):
        reconstruct_fifo_lots([fact(), replace(fact(2), account_id=2)])
    with pytest.raises(FifoReconstructionError, match="Duplicate"):
        reconstruct_fifo_lots([fact(), fact()])
    with pytest.raises(FifoReconstructionError, match="LotTransactionFact"):
        reconstruct_fifo_lots([cast(LotTransactionFact, object())])
    with pytest.raises(FifoReconstructionError, match="Multiple Account"):
        reconstruct_fifo_lots([fact()], account_id=2)
    assert reconstruct_fifo_lots([], account_id=7).account_id == 7
    assert reconstruct_fifo_lots([]).is_fully_resolved


@pytest.mark.parametrize("quantities", [("1", "1", "1"), ("0.1", "1.9", "1"), ("3",), ("4",)])
def test_every_lot_quantity_and_basis_invariants(quantities: tuple[str, ...]) -> None:
    history = [fact(), replace(fact(2), quantity=Decimal("2"), cash_amount=Decimal("17.23"))]
    history += [
        replace(fact(id_ + 3, TransactionType.SELL), quantity=Decimal(quantity))
        for id_, quantity in enumerate(quantities)
    ]
    result = reconstruct_fifo_lots(reversed(history))
    for lot in result.lots:
        matches = [
            match
            for match in result.disposal_matches
            if match.source_buy_transaction_id == lot.source_buy_transaction_id
        ]
        disposed = sum(decimal_to_scaled_int(match.matched_quantity, 12) for match in matches)
        remaining = decimal_to_scaled_int(lot.remaining_quantity, 12)
        assert decimal_to_scaled_int(lot.original_quantity, 12) == disposed + remaining
        removed = sum((match.removed_basis.amount for match in matches), Fraction(0))
        assert lot.original_basis.amount == removed + lot.remaining_basis.amount
        if not remaining:
            assert lot.remaining_basis.amount == 0
            assert removed == lot.original_basis.amount
    assert result.open_lots == tuple(lot for lot in result.lots if lot.remaining_quantity > 0)


def test_tiny_decimal_context_preserves_cash_quantity_and_repeating_allocation() -> None:
    buy = replace(fact(), quantity=Decimal("3.000000000003"), cash_amount=Decimal("100.12345678"))
    sell = replace(fact(2, TransactionType.SELL), quantity=Decimal("1.000000000001"))
    with localcontext(Context(prec=3)):
        result = reconstruct_fifo_lots([sell, buy])
        lot = result.lots[0]
        assert lot.original_quantity.as_tuple() == buy.quantity.as_tuple()  # type: ignore[union-attr]
        assert lot.remaining_quantity == Decimal("2.000000000002")
        expected = Fraction(10012345678, 10**8)
        assert lot.original_basis.amount == expected
        assert lot.remaining_basis.amount == expected * Fraction(2, 3)
        assert result.disposal_matches[0].removed_basis.amount == expected / 3
        summaries = summarize_account(result)
        aggregate = aggregate_portfolio_summaries([summaries, summaries])[0]
        assert aggregate.open_long_quantity == Decimal("4.000000000004")
        assert aggregate.remaining_basis_by_currency["USD"].amount == expected * Fraction(4, 3)


@pytest.mark.parametrize(
    ("text", "scale", "units"),
    [
        ("-1.23000", 2, -123),
        ("1E-12", 12, 1),
        ("1E8", 8, 10**16),
        ("0E-100", 12, 0),
        ("9999999999999999.999999999999", 12, 10**28 - 1),
    ],
)
def test_shared_exact_conversion_roundtrip(text: str, scale: int, units: int) -> None:
    with localcontext(Context(prec=3)):
        assert decimal_to_scaled_int(Decimal(text), scale) == units
        assert scaled_int_to_decimal(units, scale) == Decimal(text)


@pytest.mark.parametrize("value", [Decimal("1E-13"), Decimal("NaN"), Decimal("Infinity"), 1.1])
def test_shared_conversion_never_rounds_or_accepts_float(value: Decimal) -> None:
    with pytest.raises(ValueError):
        decimal_to_scaled_int(value, 12)


def test_future_buy_never_repairs_prior_unmatched_sell() -> None:
    history = [
        replace(fact(1, TransactionType.SELL), quantity=Decimal("4")),
        replace(fact(2), effective_date=date(2020, 1, 2)),
    ]
    result = reconstruct_fifo_lots(reversed(history))
    assert result.disposal_matches == ()
    assert result.unmatched_sells[0].unmatched_quantity == Decimal("4")
    assert result.lots[0].remaining_quantity == Decimal("3")
    assert result.lots[0].remaining_basis.amount == Fraction(100)


def test_portfolio_basis_partitions_and_same_currency_addition_remain_exact() -> None:
    first = reconstruct_fifo_lots([fact()])
    second = reconstruct_fifo_lots(
        [
            replace(fact(2), account_id=2, cash_amount=Decimal("50")),
            replace(fact(3), account_id=2, currency_code="RUB", cash_amount=Decimal("45000")),
        ]
    )
    with localcontext(Context(prec=3)):
        summary = aggregate_portfolio_summaries(
            [
                summarize_account(first),
                summarize_account(second),
            ]
        )[0]
    assert summary.open_long_quantity == Decimal("9")
    assert summary.remaining_basis_by_currency == {
        "USD": ExactMoney(Fraction(150), "USD"),
        "RUB": ExactMoney(Fraction(45000), "RUB"),
    }
    assert summary.is_fully_resolved
