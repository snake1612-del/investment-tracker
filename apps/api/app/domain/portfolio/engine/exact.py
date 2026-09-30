"""Small context-independent conversions shared by F003 and F004."""

from decimal import Decimal


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
