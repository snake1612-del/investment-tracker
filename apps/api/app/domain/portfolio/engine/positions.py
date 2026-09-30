"""Pure position-quantity reconstruction approved by Decision F003."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from app.domain.portfolio.engine.exact import decimal_to_scaled_int, scaled_int_to_decimal
from app.domain.transactions import CanonicalTransaction, TransactionType


class PositionReconstructionError(ValueError):
    """Canonical history cannot be reconstructed without changing its facts."""


def _quantity_units(quantity: Decimal) -> int:
    """Convert exactly to 10^-12 units using Decimal's stored digits, not context arithmetic."""
    if not isinstance(quantity, Decimal) or not quantity.is_finite() or quantity < 0:
        raise PositionReconstructionError("Canonical quantity must be a finite magnitude")

    try:
        return decimal_to_scaled_int(quantity, 12)
    except ValueError as error:
        raise PositionReconstructionError("Canonical quantity exceeds scale 12") from error


def _decimal_from_units(units: int) -> Decimal:
    """Construct the exact result without consulting the ambient Decimal context."""
    return scaled_int_to_decimal(units, 12)


def reconstruct_positions(
    canonical_transactions: Iterable[CanonicalTransaction], as_of_date: date
) -> dict[int, Decimal]:
    """Aggregate all Account instruments by effective date in one pass."""
    units_by_instrument: dict[int, int] = {}
    for transaction in canonical_transactions:
        if transaction.effective_date > as_of_date:
            continue

        match transaction.type:
            case TransactionType.BUY | TransactionType.SELL:
                if transaction.instrument_id is None or transaction.quantity is None:
                    raise PositionReconstructionError("Trade lacks instrument identity or quantity")
                quantity_units = _quantity_units(transaction.quantity)
                effect = (
                    quantity_units if transaction.type is TransactionType.BUY else -quantity_units
                )
                instrument_id = transaction.instrument_id
                units_by_instrument[instrument_id] = (
                    units_by_instrument.get(instrument_id, 0) + effect
                )
            case TransactionType.DEPOSIT:
                pass
            case TransactionType.WITHDRAWAL:
                pass
            case TransactionType.DIVIDEND:
                pass
            case TransactionType.COUPON:
                pass
            case TransactionType.FEE:
                pass
            case TransactionType.TAX:
                pass
            case _:
                raise PositionReconstructionError("Unknown transaction quantity effect")

    return {
        instrument_id: _decimal_from_units(units)
        for instrument_id, units in units_by_instrument.items()
    }
