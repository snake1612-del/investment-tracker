"""F008 cash reconstruction: exact scale-eight integer arithmetic, no persistence."""

from collections.abc import Iterable
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal

from app.domain.portfolio.engine.exact import decimal_to_scaled_int, scaled_int_to_decimal
from app.domain.transactions import (
    CanonicalTransaction,
    TransactionType,
    fits_numeric_column,
    valid_currency_code,
)


class InvalidMoneyHistory(RuntimeError):
    """Persisted canonical facts violate a reconstruction invariant, not a read request."""


@dataclass(frozen=True)
class CurrencyMoneySummary:
    currency_code: str
    cash_balance: Decimal
    deposits: Decimal
    withdrawals: Decimal
    buy_trade_cash_outflow: Decimal
    sell_trade_cash_inflow: Decimal
    gross_dividend_income: Decimal
    gross_coupon_income: Decimal
    gross_investment_income: Decimal
    fees_paid: Decimal
    taxes_paid_or_withheld: Decimal


MONEY_FIELDS = tuple(field.name for field in fields(CurrencyMoneySummary)[1:])
_EFFECTS = {
    TransactionType.DEPOSIT: (1, "deposits"),
    TransactionType.WITHDRAWAL: (-1, "withdrawals"),
    TransactionType.BUY: (-1, "buy_trade_cash_outflow"),
    TransactionType.SELL: (1, "sell_trade_cash_inflow"),
    TransactionType.DIVIDEND: (1, "gross_dividend_income"),
    TransactionType.COUPON: (1, "gross_coupon_income"),
    TransactionType.FEE: (-1, "fees_paid"),
    TransactionType.TAX: (-1, "taxes_paid_or_withheld"),
}


def _validated_units(transaction: CanonicalTransaction) -> int:
    if not isinstance(transaction.type, TransactionType) or transaction.type not in _EFFECTS:
        raise InvalidMoneyHistory("Unknown canonical transaction type")
    if not isinstance(transaction.effective_date, date):
        raise InvalidMoneyHistory("Missing canonical effective date")
    if not isinstance(transaction.currency_code, str) or not valid_currency_code(
        transaction.currency_code
    ):
        raise InvalidMoneyHistory("Malformed canonical currency")
    amount = transaction.cash_amount
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise InvalidMoneyHistory("Malformed canonical cash amount")
    try:
        units = decimal_to_scaled_int(amount, 8)
    except ValueError as exc:
        raise InvalidMoneyHistory("Canonical cash is not exact at scale eight") from exc
    if units >= 10**24:
        raise InvalidMoneyHistory("Canonical cash exceeds NUMERIC(24,8)")
    kind = transaction.type
    if transaction.instrument_id is not None and (
        type(transaction.instrument_id) is not int or transaction.instrument_id <= 0
    ):
        raise InvalidMoneyHistory("Malformed Instrument identity")
    if kind in {TransactionType.BUY, TransactionType.SELL}:
        if transaction.instrument_id is None:
            raise InvalidMoneyHistory("Trade has no Instrument")
        for value in (transaction.quantity, transaction.price):
            if (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or value <= 0
                or not fits_numeric_column(value, precision=28, scale=12)
            ):
                raise InvalidMoneyHistory("Malformed canonical trade values")
    else:
        if any(
            value is not None
            for value in (transaction.quantity, transaction.price, transaction.settlement_date)
        ):
            raise InvalidMoneyHistory("Non-trade contains trade-only facts")
        if kind in {TransactionType.DIVIDEND, TransactionType.COUPON}:
            if transaction.instrument_id is None:
                raise InvalidMoneyHistory("Income has no Instrument")
        elif kind in {TransactionType.DEPOSIT, TransactionType.WITHDRAWAL}:
            if transaction.instrument_id is not None:
                raise InvalidMoneyHistory("External flow contains an Instrument")
    return units


def _summaries(buckets: dict[str, dict[str, int]]) -> tuple[CurrencyMoneySummary, ...]:
    return tuple(
        CurrencyMoneySummary(
            currency, **{field: scaled_int_to_decimal(bucket[field], 8) for field in MONEY_FIELDS}
        )
        for currency, bucket in sorted(buckets.items())
    )


def cash_effect_units(transaction: CanonicalTransaction) -> int:
    """Validated F008 signed cash effect, reusable by chronological reconstruction."""
    units = _validated_units(transaction)
    return _EFFECTS[transaction.type][0] * units


def reconstruct_money_summary(
    transactions: Iterable[CanonicalTransaction], as_of_date: date
) -> tuple[CurrencyMoneySummary, ...]:
    if not isinstance(as_of_date, date):
        raise ValueError("An explicit as_of_date is required")
    buckets: dict[str, dict[str, int]] = {}
    for transaction in transactions:
        # Validate even future facts: malformed history is never silently skipped.
        units = _validated_units(transaction)
        if transaction.effective_date > as_of_date:
            continue
        bucket = buckets.setdefault(transaction.currency_code, dict.fromkeys(MONEY_FIELDS, 0))
        sign, category = _EFFECTS[transaction.type]
        bucket["cash_balance"] += sign * units
        bucket[category] += units
        if transaction.type in {TransactionType.DIVIDEND, TransactionType.COUPON}:
            bucket["gross_investment_income"] += units
    return _summaries(buckets)


def aggregate_money_summaries(
    accounts: Iterable[tuple[CurrencyMoneySummary, ...]],
) -> tuple[CurrencyMoneySummary, ...]:
    """Combine already reconstructed Accounts, preserving active zero currency buckets."""
    buckets: dict[str, dict[str, int]] = {}
    for account in accounts:
        for summary in account:
            bucket = buckets.setdefault(summary.currency_code, dict.fromkeys(MONEY_FIELDS, 0))
            for field in MONEY_FIELDS:
                bucket[field] += decimal_to_scaled_int(getattr(summary, field), 8)
    return _summaries(buckets)
