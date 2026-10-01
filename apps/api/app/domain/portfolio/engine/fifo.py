"""Exact, recomputable Account FIFO lots and currency-partitioned basis (F004)."""

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction
from types import MappingProxyType

from app.domain.portfolio.engine.exact import decimal_to_scaled_int, scaled_int_to_decimal
from app.domain.transactions import TransactionType, valid_currency_code


class FifoReconstructionError(ValueError):
    """Required F004 facts cannot be reconstructed without fabrication."""


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


@dataclass(frozen=True)
class LotTransactionFact:
    transaction_id: int
    account_id: int
    type: TransactionType
    instrument_id: int | None
    quantity: Decimal | None
    cash_amount: Decimal | None
    currency_code: str | None
    effective_date: date


@dataclass(frozen=True)
class AcquisitionLot:
    source_buy_transaction_id: int
    instrument_id: int
    acquisition_effective_date: date
    original_quantity: Decimal
    remaining_quantity: Decimal
    original_basis: ExactMoney
    remaining_basis: ExactMoney


@dataclass(frozen=True)
class DisposalMatch:
    source_sell_transaction_id: int
    source_buy_transaction_id: int
    instrument_id: int
    matched_quantity: Decimal
    removed_basis: ExactMoney


@dataclass(frozen=True)
class UnmatchedSell:
    source_sell_transaction_id: int
    instrument_id: int
    effective_date: date
    unmatched_quantity: Decimal


@dataclass(frozen=True)
class FifoReconstruction:
    account_id: int | None
    lots: tuple[AcquisitionLot, ...]
    disposal_matches: tuple[DisposalMatch, ...]
    unmatched_sells: tuple[UnmatchedSell, ...]

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unmatched_sells

    @property
    def open_lots(self) -> tuple[AcquisitionLot, ...]:
        return tuple(lot for lot in self.lots if lot.remaining_quantity > 0)


@dataclass(frozen=True)
class AccountCostBasisSummary:
    instrument_id: int
    open_long_quantity: Decimal
    remaining_basis_by_currency: Mapping[str, ExactMoney]
    unmatched_sell_quantity: Decimal

    def __post_init__(self) -> None:
        basis = dict(self.remaining_basis_by_currency)
        if any(currency != money.currency_code for currency, money in basis.items()):
            raise ValueError("Basis currency partition is inconsistent")
        object.__setattr__(self, "remaining_basis_by_currency", MappingProxyType(basis))

    @property
    def is_fully_resolved(self) -> bool:
        return self.unmatched_sell_quantity == 0


@dataclass(frozen=True)
class PortfolioCostBasisSummary(AccountCostBasisSummary):
    """Same fields, aggregated only after independent Account reconstruction."""


@dataclass
class _WorkingLot:
    fact: LotTransactionFact
    original_units: int
    remaining_units: int
    basis: ExactMoney


def _identity(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise FifoReconstructionError(f"Invalid {name}")


def _quantity(fact: LotTransactionFact) -> int:
    if fact.quantity is None:
        raise FifoReconstructionError("Trade lacks quantity")
    try:
        units = decimal_to_scaled_int(fact.quantity, 12)
    except ValueError as error:
        raise FifoReconstructionError("Invalid trade quantity") from error
    if units <= 0:
        raise FifoReconstructionError("Trade quantity must be positive for lot allocation")
    return units


def _basis(fact: LotTransactionFact) -> ExactMoney:
    if fact.cash_amount is None or fact.currency_code is None:
        raise FifoReconstructionError("BUY lacks acquisition basis or currency")
    try:
        units = decimal_to_scaled_int(fact.cash_amount, 8)
        if units < 0:
            raise ValueError("Negative canonical basis")
        return ExactMoney(Fraction(units, 10**8), fact.currency_code)
    except ValueError as error:
        raise FifoReconstructionError("Invalid BUY acquisition basis") from error


def reconstruct_fifo_lots(
    transactions: Iterable[LotTransactionFact], *, account_id: int | None = None
) -> FifoReconstruction:
    """One Account history; optional identity preserves empty Account reconstructions."""
    if account_id is not None:
        _identity(account_id, "Account identity")
    streams: dict[int, list[LotTransactionFact]] = {}
    seen_ids: set[int] = set()
    for fact in transactions:
        if not isinstance(fact, LotTransactionFact):
            raise FifoReconstructionError("FIFO requires LotTransactionFact inputs")
        _identity(fact.account_id, "Account identity")
        if account_id is None:
            account_id = fact.account_id
        if account_id != fact.account_id:
            raise FifoReconstructionError("Multiple Account identities in FIFO input")
        match fact.type:
            case TransactionType.BUY | TransactionType.SELL:
                _identity(fact.transaction_id, "transaction identity")
                if fact.transaction_id in seen_ids:
                    raise FifoReconstructionError("Duplicate transaction identity")
                seen_ids.add(fact.transaction_id)
                if fact.instrument_id is None:
                    raise FifoReconstructionError("Trade lacks Instrument identity")
                _identity(fact.instrument_id, "Instrument identity")
                if type(fact.effective_date) is not date:
                    raise FifoReconstructionError("Trade lacks effective date")
                _quantity(fact)
                if fact.type is TransactionType.BUY:
                    _basis(fact)
                streams.setdefault(fact.instrument_id, []).append(fact)
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
                raise FifoReconstructionError("Unknown transaction lot effect")

    lots: list[AcquisitionLot] = []
    matches: list[DisposalMatch] = []
    unmatched: list[UnmatchedSell] = []
    for instrument_id, facts in sorted(streams.items()):
        working: list[_WorkingLot] = []
        open_lots: deque[_WorkingLot] = deque()
        for fact in sorted(facts, key=lambda item: (item.effective_date, item.transaction_id)):
            units = _quantity(fact)
            if fact.type is TransactionType.BUY:
                lot = _WorkingLot(fact, units, units, _basis(fact))
                working.append(lot)
                open_lots.append(lot)
                continue
            while units and open_lots:
                lot = open_lots[0]
                matched = min(units, lot.remaining_units)
                matches.append(
                    DisposalMatch(
                        fact.transaction_id,
                        lot.fact.transaction_id,
                        instrument_id,
                        scaled_int_to_decimal(matched, 12),
                        lot.basis.allocated(matched, lot.original_units),
                    )
                )
                units -= matched
                lot.remaining_units -= matched
                if not lot.remaining_units:
                    open_lots.popleft()
            if units:
                unmatched.append(
                    UnmatchedSell(
                        fact.transaction_id,
                        instrument_id,
                        fact.effective_date,
                        scaled_int_to_decimal(units, 12),
                    )
                )
        lots.extend(
            AcquisitionLot(
                lot.fact.transaction_id,
                instrument_id,
                lot.fact.effective_date,
                scaled_int_to_decimal(lot.original_units, 12),
                scaled_int_to_decimal(lot.remaining_units, 12),
                lot.basis,
                lot.basis.allocated(lot.remaining_units, lot.original_units),
            )
            for lot in working
        )
    return FifoReconstruction(account_id, tuple(lots), tuple(matches), tuple(unmatched))


def summarize_account(reconstruction: FifoReconstruction) -> tuple[AccountCostBasisSummary, ...]:
    quantities: dict[int, int] = {}
    basis: dict[int, dict[str, ExactMoney]] = {}
    unmatched: dict[int, int] = {}
    for lot in reconstruction.lots:
        instrument = lot.instrument_id
        units = decimal_to_scaled_int(lot.remaining_quantity, 12)
        quantities[instrument] = quantities.get(instrument, 0) + units
        if units:
            partition = basis.setdefault(instrument, {})
            currency = lot.remaining_basis.currency_code
            partition[currency] = partition.get(currency, ExactMoney(Fraction(0), currency)) + (
                lot.remaining_basis
            )
    for sell in reconstruction.unmatched_sells:
        instrument = sell.instrument_id
        unmatched[instrument] = unmatched.get(instrument, 0) + decimal_to_scaled_int(
            sell.unmatched_quantity, 12
        )
    return tuple(
        AccountCostBasisSummary(
            instrument,
            scaled_int_to_decimal(quantities.get(instrument, 0), 12),
            basis.get(instrument, {}),
            scaled_int_to_decimal(unmatched.get(instrument, 0), 12),
        )
        for instrument in sorted(quantities.keys() | unmatched.keys())
    )


def aggregate_portfolio_summaries(
    summaries: Iterable[Iterable[AccountCostBasisSummary]],
) -> tuple[PortfolioCostBasisSummary, ...]:
    quantities: dict[int, int] = {}
    unmatched: dict[int, int] = {}
    basis: dict[int, dict[str, ExactMoney]] = {}
    for account in summaries:
        for summary in account:
            instrument = summary.instrument_id
            quantities[instrument] = quantities.get(instrument, 0) + decimal_to_scaled_int(
                summary.open_long_quantity, 12
            )
            unmatched[instrument] = unmatched.get(instrument, 0) + decimal_to_scaled_int(
                summary.unmatched_sell_quantity, 12
            )
            partition = basis.setdefault(instrument, {})
            for currency, money in summary.remaining_basis_by_currency.items():
                partition[currency] = partition.get(currency, ExactMoney(Fraction(0), currency)) + (
                    money
                )
    return tuple(
        PortfolioCostBasisSummary(
            instrument,
            scaled_int_to_decimal(quantities[instrument], 12),
            basis[instrument],
            scaled_int_to_decimal(unmatched[instrument], 12),
        )
        for instrument in sorted(quantities)
    )
