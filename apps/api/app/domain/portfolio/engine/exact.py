"""Small context-independent conversions shared by F003 and F004."""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.domain.transactions import valid_currency_code


@dataclass(frozen=True)
class ExactMoney:
    amount: Fraction
    currency_code: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.amount, Fraction)
            or not isinstance(self.currency_code, str)
            or not valid_currency_code(self.currency_code)
        ):
            raise ValueError("ExactMoney requires a Fraction and canonical currency code")

    def __add__(self, other: ExactMoney) -> ExactMoney:
        if self.currency_code != other.currency_code:
            raise ValueError("Cannot add basis in different currencies")
        return ExactMoney(self.amount + other.amount, self.currency_code)

    def __sub__(self, other: ExactMoney) -> ExactMoney:
        if self.currency_code != other.currency_code:
            raise ValueError("Cannot subtract money in different currencies")
        return ExactMoney(self.amount - other.amount, self.currency_code)

    def allocated(self, quantity_units: int, original_units: int) -> ExactMoney:
        return ExactMoney(
            self.amount * Fraction(quantity_units, original_units), self.currency_code
        )


def decimal_to_scaled_int(value: Decimal, scale: int) -> int:
    """Reject rather than round values not exactly representable at the given scale."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("An exact finite Decimal is required")
    if type(scale) is not int or scale < 0:
        raise ValueError("Scale must be a non-negative integer")
    parts = value.as_tuple()
    exponent = parts.exponent
    if not isinstance(exponent, int):
        raise ValueError("Invalid Decimal exponent")
    coefficient = 0
    for digit in parts.digits:
        coefficient = coefficient * 10 + digit
    shift = exponent + scale
    if shift >= 0:
        units = coefficient * 10**shift
    else:
        units, remainder = divmod(coefficient, 10 ** (-shift))
        if remainder:
            raise ValueError(f"Value exceeds exact scale {scale}")
    return -units if parts.sign else units


def scaled_int_to_decimal(value: int, scale: int) -> Decimal:
    """Construct a Decimal directly from digits, without context arithmetic."""
    if type(value) is not int or type(scale) is not int or scale < 0:
        raise ValueError("Integer units and non-negative integer scale are required")
    digits = tuple(int(digit) for digit in str(abs(value)))
    return Decimal((int(value < 0), digits, -scale))
