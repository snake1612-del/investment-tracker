from datetime import date
from decimal import Decimal

import pytest

from app.domain.transactions import CanonicalTransaction, InvalidTransaction, TransactionType


def test_valid_deposit_uses_canonical_unsigned_facts() -> None:
    transaction = CanonicalTransaction.deposit(7, Decimal("100.25"), "USD", date(2026, 9, 27))

    assert transaction.type is TransactionType.DEPOSIT
    assert transaction.cash_amount == Decimal("100.25")
    assert isinstance(transaction.cash_amount, Decimal)
    assert transaction.instrument_id is None
    assert transaction.related_transaction_id is None
    assert transaction.quantity is None
    assert transaction.price is None
    assert transaction.settlement_date is None


@pytest.mark.parametrize("amount", [Decimal("-1"), Decimal("0")])
def test_deposit_rejects_non_positive_amount(amount: Decimal) -> None:
    with pytest.raises(InvalidTransaction):
        CanonicalTransaction.deposit(7, amount, "USD", date(2026, 9, 27))


@pytest.mark.parametrize("currency", ["usd", "US", "US1", "ÜSD"])
def test_deposit_requires_structural_currency_code(currency: str) -> None:
    with pytest.raises(InvalidTransaction):
        CanonicalTransaction.deposit(7, Decimal("1"), currency, date(2026, 9, 27))


@pytest.mark.parametrize("amount", ["1.123456789", "10000000000000000"])
def test_deposit_rejects_values_not_exactly_storable_as_numeric_24_8(amount: str) -> None:
    with pytest.raises(InvalidTransaction, match="NUMERIC\\(24,8\\)"):
        CanonicalTransaction.deposit(7, Decimal(amount), "USD", date(2026, 9, 27))


@pytest.mark.parametrize("amount", ["123456.12500001", "1.2300000000"])
def test_deposit_accepts_exactly_storable_values_and_cosmetic_zeroes(amount: str) -> None:
    transaction = CanonicalTransaction.deposit(7, Decimal(amount), "USD", date(2026, 9, 27))
    assert transaction.cash_amount == Decimal(amount)
