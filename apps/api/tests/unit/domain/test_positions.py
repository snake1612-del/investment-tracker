from dataclasses import replace
from datetime import date
from decimal import Context, Decimal, localcontext

import pytest

from app.domain.portfolio.engine.positions import PositionReconstructionError, reconstruct_positions
from app.domain.transactions import CanonicalTransaction, TransactionType

AS_OF = date(2020, 1, 10)


def fact(
    transaction_type: TransactionType,
    quantity: str | None = None,
    *,
    instrument_id: int | None = 1,
    effective_date: date = AS_OF,
    settlement_date: date | None = None,
) -> CanonicalTransaction:
    return CanonicalTransaction(
        account_id=1,
        type=transaction_type,
        cash_amount=Decimal("999"),
        currency_code="USD",
        effective_date=effective_date,
        instrument_id=instrument_id,
        quantity=Decimal(quantity) if quantity is not None else None,
        price=Decimal("17"),
        settlement_date=settlement_date,
    )


@pytest.mark.parametrize(
    ("history", "expected"),
    [
        ([fact(TransactionType.BUY, "10")], Decimal("10")),
        (
            [fact(TransactionType.BUY, "10"), fact(TransactionType.SELL, "4")],
            Decimal("6"),
        ),
        ([fact(TransactionType.SELL, "4")], Decimal("-4")),
        (
            [fact(TransactionType.BUY, "10"), fact(TransactionType.SELL, "10")],
            Decimal("0"),
        ),
        (
            [
                fact(TransactionType.BUY, "1.123456789012"),
                fact(TransactionType.BUY, "2.000000000001"),
            ],
            Decimal("3.123456789013"),
        ),
    ],
)
def test_reference_quantities(history: list[CanonicalTransaction], expected: Decimal) -> None:
    assert reconstruct_positions(history, AS_OF) == {1: expected}


def test_empty_history_and_multiple_instrument_identities() -> None:
    assert reconstruct_positions([], AS_OF) == {}
    history = [
        fact(TransactionType.BUY, "3", instrument_id=2),
        fact(TransactionType.BUY, "7", instrument_id=1),
        fact(TransactionType.SELL, "1", instrument_id=2),
    ]
    assert reconstruct_positions(history, AS_OF) == {1: Decimal("7"), 2: Decimal("2")}
    # Same-name instruments remain distinct because reconstruction sees only their IDs.


def test_effective_date_boundary_backdating_and_settlement() -> None:
    history = [
        fact(
            TransactionType.BUY,
            "10",
            effective_date=date(2020, 1, 9),
            settlement_date=date(2020, 2, 1),
        ),
        fact(TransactionType.SELL, "4", effective_date=date(2020, 1, 10)),
        fact(TransactionType.BUY, "100", effective_date=date(2020, 1, 11)),
        fact(TransactionType.SELL, "200", effective_date=date(2020, 1, 11)),
    ]
    assert reconstruct_positions(history, date(2020, 1, 8)) == {}
    assert reconstruct_positions(history, date(2020, 1, 9)) == {1: Decimal("10")}
    assert reconstruct_positions(history, AS_OF) == {1: Decimal("6")}
    assert reconstruct_positions(list(reversed(history)), AS_OF) == {1: Decimal("6")}


def test_same_date_and_insertion_order_do_not_change_quantity() -> None:
    history = [fact(TransactionType.SELL, "4"), fact(TransactionType.BUY, "10")]
    assert reconstruct_positions(history, AS_OF) == reconstruct_positions(
        list(reversed(history)), AS_OF
    )


def test_price_cash_currency_and_settlement_do_not_affect_quantity() -> None:
    original = fact(TransactionType.BUY, "2")
    altered = replace(
        original,
        price=Decimal("900"),
        cash_amount=Decimal("1"),
        currency_code="EUR",
        settlement_date=date(2020, 2, 1),
    )
    assert reconstruct_positions([original], AS_OF) == reconstruct_positions([altered], AS_OF)


@pytest.mark.parametrize(
    "transaction_type",
    [
        TransactionType.DEPOSIT,
        TransactionType.WITHDRAWAL,
        TransactionType.DIVIDEND,
        TransactionType.COUPON,
        TransactionType.FEE,
        TransactionType.TAX,
    ],
)
def test_known_non_trade_type_has_explicit_zero_effect(transaction_type: TransactionType) -> None:
    assert reconstruct_positions([fact(transaction_type, "100")], AS_OF) == {}


def test_quantity_semantics_must_be_updated_when_transaction_enum_expands() -> None:
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


@pytest.mark.parametrize("transaction_type", [TransactionType.BUY, TransactionType.SELL])
def test_missing_trade_quantity_or_instrument_fails(transaction_type: TransactionType) -> None:
    with pytest.raises(PositionReconstructionError):
        reconstruct_positions([fact(transaction_type, instrument_id=1)], AS_OF)
    with pytest.raises(PositionReconstructionError):
        reconstruct_positions([fact(transaction_type, "1", instrument_id=None)], AS_OF)


def test_exact_aggregation_is_independent_of_ambient_decimal_context() -> None:
    history = [
        fact(TransactionType.BUY, "9999999999999999.999999999999"),
        fact(TransactionType.BUY, "9999999999999999.999999999999"),
        fact(TransactionType.SELL, "0.000000000001"),
    ]
    with localcontext(Context(prec=3)):
        result = reconstruct_positions(history, AS_OF)[1]
        assert result.as_tuple() == Decimal("19999999999999999.999999999997").as_tuple()
    assert result == Decimal("19999999999999999.999999999997")


def test_smallest_units_and_mixed_sign_effects_are_exact() -> None:
    history = [
        fact(TransactionType.BUY, "0.000000000001"),
        fact(TransactionType.SELL, "0.000000000002"),
        fact(TransactionType.BUY, "0.000000000001"),
    ]
    assert reconstruct_positions(history, AS_OF) == {1: Decimal("0")}
    assert reconstruct_positions(history[:2], AS_OF) == {1: Decimal("-0.000000000001")}


@pytest.mark.parametrize("transaction_type", [TransactionType.BUY, TransactionType.SELL])
def test_more_than_twelve_fractional_places_fails(transaction_type: TransactionType) -> None:
    with localcontext(Context(prec=3)):
        with pytest.raises(PositionReconstructionError):
            reconstruct_positions([fact(transaction_type, "0.0000000000001")], AS_OF)


def test_cosmetic_trailing_zeroes_do_not_lose_exactness() -> None:
    assert reconstruct_positions([fact(TransactionType.BUY, "1.2300000000000")], AS_OF) == {
        1: Decimal("1.23")
    }
