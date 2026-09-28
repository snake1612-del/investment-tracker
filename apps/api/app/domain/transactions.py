"""Canonical transaction rules approved for the first DEPOSIT slice."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class TransactionType(StrEnum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    COUPON = "COUPON"
    FEE = "FEE"
    TAX = "TAX"


class InvalidTransaction(ValueError):
    """A canonical transaction violates an approved domain rule."""


def valid_currency_code(value: str) -> bool:
    return re.fullmatch(r"[A-Z]{3}", value) is not None


def fits_cash_amount_column(value: Decimal) -> bool:
    """Check exact NUMERIC(24,8) fit without rounding or a decimal context."""
    digits = value.as_tuple().digits
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        return False
    while digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    return exponent >= -8 and len(digits) + exponent <= 16


@dataclass(frozen=True)
class CanonicalTransaction:
    account_id: int
    type: TransactionType
    cash_amount: Decimal
    currency_code: str
    effective_date: date
    instrument_id: int | None = None
    related_transaction_id: int | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    settlement_date: date | None = None
    note: str | None = None

    @classmethod
    def deposit(
        cls,
        account_id: int,
        cash_amount: Decimal,
        currency_code: str,
        effective_date: date,
        note: str | None = None,
    ) -> CanonicalTransaction:
        if not isinstance(cash_amount, Decimal) or not cash_amount.is_finite() or cash_amount <= 0:
            raise InvalidTransaction("Deposit cash_amount must be a positive finite decimal")
        if not fits_cash_amount_column(cash_amount):
            raise InvalidTransaction(
                "Deposit cash_amount cannot be stored exactly as NUMERIC(24,8)"
            )
        if not valid_currency_code(currency_code):
            raise InvalidTransaction("Currency code must contain three uppercase ASCII letters")
        if not isinstance(effective_date, date):
            raise InvalidTransaction("Deposit effective_date is required")
        return cls(
            account_id=account_id,
            type=TransactionType.DEPOSIT,
            cash_amount=cash_amount,
            currency_code=currency_code,
            effective_date=effective_date,
            note=note,
        )
