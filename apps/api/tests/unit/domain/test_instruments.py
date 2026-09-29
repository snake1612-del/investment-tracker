import pytest

from app.domain.instruments import InvalidInstrument, normalized_instrument_name


@pytest.mark.parametrize(
    ("provided", "expected"),
    [
        ("Share", "Share"),
        ("  Share  ", "Share"),
        ("A  B", "A  B"),
        ("  Акция 東京  ", "Акция 東京"),
        ("x" * 200, "x" * 200),
    ],
)
def test_valid_manual_instrument_name(provided: str, expected: str) -> None:
    assert normalized_instrument_name(provided) == expected


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_invalid_manual_instrument_name(name: str) -> None:
    with pytest.raises(InvalidInstrument):
        normalized_instrument_name(name)
