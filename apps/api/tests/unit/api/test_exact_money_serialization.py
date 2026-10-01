import sys
from fractions import Fraction
from math import gcd

import pytest

from app.api.schemas import ExactMoneyRead, _integer_to_decimal_string
from app.domain.portfolio.engine.fifo import ExactMoney


@pytest.mark.parametrize("negative", [False, True])
def test_rational_over_4300_digits_at_standard_runtime_limit(negative: bool) -> None:
    limit_before = sys.get_int_max_str_digits()
    assert limit_before == sys.int_info.default_max_str_digits == 4300
    denominator = 10**4500
    numerator = denominator + 1
    if negative:
        numerator = -numerator
    value = Fraction(numerator, denominator)
    assert gcd(value.numerator, value.denominator) == 1
    with pytest.raises(ValueError, match="limit"):
        str(value.numerator)
    with pytest.raises(ValueError, match="limit"):
        str(value.denominator)

    result = ExactMoneyRead.from_money(ExactMoney(value, "USD")).model_dump(mode="json")
    expected_numerator = ("-" if negative else "") + "1" + "0" * 4499 + "1"
    expected_denominator = "1" + "0" * 4500
    assert result == {
        "currency_code": "USD",
        "amount": {"numerator": expected_numerator, "denominator": expected_denominator},
    }
    assert len(result["amount"]["numerator"].lstrip("-")) > 4300
    assert len(result["amount"]["denominator"]) > 4300
    assert sys.get_int_max_str_digits() == limit_before


@pytest.mark.parametrize(
    ("value", "numerator", "denominator"),
    [
        (Fraction(0), "0", "1"),
        (Fraction(42), "42", "1"),
        (Fraction(-42), "-42", "1"),
        (Fraction(-6, 4), "-3", "2"),
    ],
)
def test_normal_canonical_rational_values(
    value: Fraction, numerator: str, denominator: str
) -> None:
    assert ExactMoneyRead.from_money(ExactMoney(value, "USD")).model_dump(mode="json") == {
        "currency_code": "USD",
        "amount": {"numerator": numerator, "denominator": denominator},
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (42, "42"),
        (-42, "-42"),
        (10**9, "1000000000"),
        (10**27 + 42, "1" + "0" * 25 + "42"),
        (-(10**27) - 42, "-1" + "0" * 25 + "42"),
    ],
)
def test_integer_chunks_keep_sign_padding_and_canonical_digits(value: int, expected: str) -> None:
    assert _integer_to_decimal_string(value) == expected
