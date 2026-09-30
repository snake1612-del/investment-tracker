"""Canonical transaction rules approved by Decisions F001 and F002."""

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
    return fits_numeric_column(value, precision=24, scale=8)


def fits_numeric_column(value: Decimal, *, precision: int, scale: int) -> bool:
    """Check exact NUMERIC(p,s) representability without changing the value."""
    digits = value.as_tuple().digits
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        return False
    while len(digits) > 1 and digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    return exponent >= -scale and len(digits) + exponent <= precision - scale


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

    @classmethod
    def buy(
        cls,
        account_id: int,
        instrument_id: int,
        quantity: Decimal,
        price: Decimal,
        cash_amount: Decimal,
        currency_code: str,
        effective_date: date,
        settlement_date: date | None = None,
        note: str | None = None,
    ) -> CanonicalTransaction:
        return cls._manual_trade(
            TransactionType.BUY,
            account_id,
            instrument_id,
            quantity,
            price,
            cash_amount,
            currency_code,
            effective_date,
            settlement_date,
            note,
        )

    @classmethod
    def sell(
        cls,
        account_id: int,
        instrument_id: int,
        quantity: Decimal,
        price: Decimal,
        cash_amount: Decimal,
        currency_code: str,
        effective_date: date,
        settlement_date: date | None = None,
        note: str | None = None,
    ) -> CanonicalTransaction:
        return cls._manual_trade(
            TransactionType.SELL,
            account_id,
            instrument_id,
            quantity,
            price,
            cash_amount,
            currency_code,
            effective_date,
            settlement_date,
            note,
        )

    @classmethod
    def _manual_trade(
        cls,
        trade_type: TransactionType,
        account_id: int,
        instrument_id: int,
        quantity: Decimal,
        price: Decimal,
        cash_amount: Decimal,
        currency_code: str,
        effective_date: date,
        settlement_date: date | None,
        note: str | None,
    ) -> CanonicalTransaction:
        if not isinstance(instrument_id, int) or instrument_id <= 0:
            raise InvalidTransaction("Manual trade requires an Instrument identity")
        for field, value, precision, scale in (
            ("quantity", quantity, 28, 12),
            ("price", price, 28, 12),
            ("cash_amount", cash_amount, 24, 8),
        ):
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise InvalidTransaction(f"Manual trade {field} must be a positive finite decimal")
            if not fits_numeric_column(value, precision=precision, scale=scale):
                raise InvalidTransaction(
                    f"Manual trade {field} cannot be stored exactly as NUMERIC({precision},{scale})"
                )
        if not valid_currency_code(currency_code):
            raise InvalidTransaction("Currency code must contain three uppercase ASCII letters")
        if not isinstance(effective_date, date):
            raise InvalidTransaction("Manual trade effective_date is required")
        if settlement_date is not None and (
            not isinstance(settlement_date, date) or settlement_date < effective_date
        ):
            raise InvalidTransaction("Settlement date must not precede effective date")
        return cls(
            account_id=account_id,
            type=trade_type,
            instrument_id=instrument_id,
            quantity=quantity,
            price=price,
            cash_amount=cash_amount,
            currency_code=currency_code,
            effective_date=effective_date,
            settlement_date=settlement_date,
            note=note,
        )
