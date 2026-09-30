from datetime import date
from decimal import Decimal

import pytest

from app.domain.transactions import CanonicalTransaction, InvalidTransaction, TransactionType


def trade(trade_type: TransactionType, **overrides: object) -> CanonicalTransaction:
    values: dict[str, object] = {
        "account_id": 1,
        "instrument_id": 2,
        "quantity": Decimal("2"),
        "price": Decimal("10"),
        "cash_amount": Decimal("19.99"),
        "currency_code": "USD",
        "effective_date": date(2020, 1, 2),
        "settlement_date": None,
    }
    values.update(overrides)
    constructor = (
        CanonicalTransaction.buy if trade_type is TransactionType.BUY else CanonicalTransaction.sell
    )
    return constructor(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("trade_type", [TransactionType.BUY, TransactionType.SELL])
def test_valid_trade_preserves_independent_facts_and_allows_oversell(
    trade_type: TransactionType,
) -> None:
    result = trade(trade_type)
    assert result.type is trade_type
    assert result.instrument_id == 2
    assert result.quantity == Decimal("2")
    assert result.price == Decimal("10")
    assert result.cash_amount == Decimal("19.99")
    assert result.related_transaction_id is None
    assert result.settlement_date is None
    assert result.effective_date == date(2020, 1, 2)


@pytest.mark.parametrize("trade_type", [TransactionType.BUY, TransactionType.SELL])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity", Decimal("0")),
        ("quantity", Decimal("-1")),
        ("price", Decimal("0")),
        ("price", Decimal("-1")),
        ("cash_amount", Decimal("0")),
        ("cash_amount", Decimal("-1")),
        ("quantity", Decimal("NaN")),
        ("instrument_id", 0),
        ("currency_code", "usd"),
        ("currency_code", "US1"),
        ("currency_code", "ÜSD"),
        ("quantity", Decimal("1.0000000000001")),
        ("price", Decimal("1.0000000000001")),
        ("cash_amount", Decimal("1.000000001")),
        ("quantity", Decimal("10000000000000000")),
        ("price", Decimal("10000000000000000")),
        ("cash_amount", Decimal("10000000000000000")),
        ("settlement_date", date(2020, 1, 1)),
    ],
)
def test_invalid_manual_trade(trade_type: TransactionType, field: str, value: object) -> None:
    with pytest.raises(InvalidTransaction):
        trade(trade_type, **{field: value})


@pytest.mark.parametrize("trade_type", [TransactionType.BUY, TransactionType.SELL])
def test_equal_settlement_and_cosmetic_decimal_zeroes_are_valid(
    trade_type: TransactionType,
) -> None:
    result = trade(
        trade_type,
        quantity=Decimal("1.2300000000000"),
        price=Decimal("1E-12"),
        cash_amount=Decimal("1.2300000000"),
        settlement_date=date(2020, 1, 2),
    )
    assert result.settlement_date == result.effective_date
    assert result.quantity == Decimal("1.2300000000000")
    assert result.cash_amount == Decimal("1.2300000000")
