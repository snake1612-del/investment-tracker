"""F009 factual market input, independent of transport and persistence."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.transactions import fits_numeric_column, valid_currency_code


@dataclass(frozen=True)
class MarketPrice:
    instrument_id: int
    price: Decimal
    currency_code: str
    effective_date: date

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not int or self.instrument_id <= 0:
            raise ValueError("Instrument identity must be positive")
        if (
            not isinstance(self.price, Decimal)
            or not self.price.is_finite()
            or self.price < 0
            or (self.price != 0 and not fits_numeric_column(self.price, precision=28, scale=12))
        ):
            raise ValueError("Price must be a non-negative exact NUMERIC(28,12) decimal")
        if not isinstance(self.currency_code, str) or not valid_currency_code(self.currency_code):
            raise ValueError("Currency must be three uppercase ASCII letters")
        if type(self.effective_date) is not date:
            raise ValueError("An effective date is required")
        if self.price == 0:
            object.__setattr__(self, "price", Decimal(0))
