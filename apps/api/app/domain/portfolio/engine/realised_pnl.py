"""F005: exact factual SELL proceeds over authoritative F004 disposal components."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from types import MappingProxyType

from app.domain.portfolio.engine.exact import decimal_to_scaled_int
from app.domain.portfolio.engine.fifo import (
    DisposalMatch,
    ExactMoney,
    FifoReconstruction,
    LotTransactionFact,
    UnmatchedSell,
)
from app.domain.transactions import TransactionType


class GrossRealisedPnlError(ValueError):
    """Factual SELL data or authoritative disposal components are inconsistent."""


class RealisedPnlUnresolvedReason(StrEnum):
    MISSING_ACQUISITION_BASIS = "MISSING_ACQUISITION_BASIS"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"


@dataclass(frozen=True)
class RealisedMatch:
    source_sell_transaction_id: int
    source_buy_transaction_id: int
    instrument_id: int
    matched_quantity: Decimal
    allocated_proceeds: ExactMoney
    removed_basis: ExactMoney

    @property
    def realised_pnl(self) -> ExactMoney | None:
        if self.unresolved_reason is not None:
            return None
        return self.allocated_proceeds - self.removed_basis

    @property
    def unresolved_reason(self) -> RealisedPnlUnresolvedReason | None:
        if self.allocated_proceeds.currency_code != self.removed_basis.currency_code:
            return RealisedPnlUnresolvedReason.CURRENCY_MISMATCH
        return None


@dataclass(frozen=True)
class UnmatchedProceeds:
    source_sell_transaction_id: int
    instrument_id: int
    unmatched_quantity: Decimal
    allocated_proceeds: ExactMoney

    @property
    def unresolved_reason(self) -> RealisedPnlUnresolvedReason:
        return RealisedPnlUnresolvedReason.MISSING_ACQUISITION_BASIS


type UnresolvedComponent = RealisedMatch | UnmatchedProceeds


@dataclass(frozen=True)
class RealisedSell:
    sell_transaction_id: int
    instrument_id: int
    effective_date: date
    total_proceeds: ExactMoney
    matches: tuple[RealisedMatch, ...]
    unmatched_proceeds: UnmatchedProceeds | None

    @property
    def resolved_matches(self) -> tuple[RealisedMatch, ...]:
        return tuple(match for match in self.matches if match.unresolved_reason is None)

    @property
    def unresolved_matches(self) -> tuple[RealisedMatch, ...]:
        return tuple(match for match in self.matches if match.unresolved_reason is not None)

    @property
    def unresolved_components(self) -> tuple[UnresolvedComponent, ...]:
        return self.unresolved_matches + (
            (self.unmatched_proceeds,) if self.unmatched_proceeds is not None else ()
        )

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_components


@dataclass(frozen=True)
class GrossRealisedPnlReconstruction:
    account_id: int | None
    sells: tuple[RealisedSell, ...]


def _currency_partition(values: Mapping[str, ExactMoney]) -> Mapping[str, ExactMoney]:
    copied = dict(values)
    if any(currency != money.currency_code for currency, money in copied.items()):
        raise GrossRealisedPnlError("Inconsistent currency partition")
    return MappingProxyType(copied)


@dataclass(frozen=True)
class AccountGrossRealisedPnlSummary:
    account_id: int | None
    resolved_pnl_by_currency: Mapping[str, ExactMoney]
    unresolved_components: tuple[UnresolvedComponent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "resolved_pnl_by_currency", _currency_partition(self.resolved_pnl_by_currency)
        )

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_components


@dataclass(frozen=True)
class AccountUnresolvedComponent:
    account_id: int | None
    component: UnresolvedComponent


@dataclass(frozen=True)
class PortfolioGrossRealisedPnlSummary:
    resolved_pnl_by_currency: Mapping[str, ExactMoney]
    unresolved_components: tuple[AccountUnresolvedComponent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "resolved_pnl_by_currency", _currency_partition(self.resolved_pnl_by_currency)
        )

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_components


def _quantity_units(quantity: Decimal | None) -> int:
    if quantity is None:
        raise GrossRealisedPnlError("Missing quantity")
    try:
        units = decimal_to_scaled_int(quantity, 12)
    except ValueError as error:
        raise GrossRealisedPnlError("Invalid exact scale-12 quantity") from error
    if units <= 0:
        raise GrossRealisedPnlError("Disposal quantity must be positive")
    return units


def _sell_proceeds(fact: LotTransactionFact) -> ExactMoney:
    if fact.cash_amount is None or fact.currency_code is None:
        raise GrossRealisedPnlError("SELL lacks factual proceeds or currency")
    try:
        units = decimal_to_scaled_int(fact.cash_amount, 8)
        if units < 0:
            raise ValueError("Negative canonical cash")
        return ExactMoney(Fraction(units, 10**8), fact.currency_code)
    except ValueError as error:
        raise GrossRealisedPnlError("Invalid exact SELL cash or currency") from error


def reconstruct_gross_realised_pnl(
    fifo: FifoReconstruction, transaction_facts: Iterable[LotTransactionFact]
) -> GrossRealisedPnlReconstruction:
    """Allocate proceeds only to supplied F004 matches; never reconstruct matching."""
    facts: dict[int, LotTransactionFact] = {}
    for fact in transaction_facts:
        if not isinstance(fact, LotTransactionFact):
            raise GrossRealisedPnlError("Expected LotTransactionFact")
        if type(fact.transaction_id) is not int or fact.transaction_id <= 0:
            raise GrossRealisedPnlError("Invalid factual transaction identity")
        if fact.transaction_id in facts:
            raise GrossRealisedPnlError("Duplicate factual transaction identity")
        facts[fact.transaction_id] = fact

    matches: dict[int, list[DisposalMatch]] = {}
    unmatched: dict[int, UnmatchedSell] = {}
    for match in fifo.disposal_matches:
        matches.setdefault(match.source_sell_transaction_id, []).append(match)
    for remainder in fifo.unmatched_sells:
        sell_id = remainder.source_sell_transaction_id
        if sell_id in unmatched:
            raise GrossRealisedPnlError("Multiple unmatched remainders for one SELL")
        unmatched[sell_id] = remainder

    sells: list[RealisedSell] = []
    for sell_id in dict.fromkeys((*matches, *unmatched)):
        fact = facts.get(sell_id)
        if fact is None or fact.type is not TransactionType.SELL:
            raise GrossRealisedPnlError("F004 reference does not resolve to a SELL fact")
        if fact.account_id != fifo.account_id:
            raise GrossRealisedPnlError("SELL Account does not match reconstruction")
        if type(fact.instrument_id) is not int or fact.instrument_id <= 0:
            raise GrossRealisedPnlError("Invalid SELL Instrument identity")
        if type(fact.effective_date) is not date:
            raise GrossRealisedPnlError("Invalid SELL effective date")
        original_units = _quantity_units(fact.quantity)
        proceeds = _sell_proceeds(fact)
        realised: list[RealisedMatch] = []
        component_units = 0
        for match in matches.get(sell_id, []):
            if match.instrument_id != fact.instrument_id:
                raise GrossRealisedPnlError("Component Instrument does not match SELL")
            units = _quantity_units(match.matched_quantity)
            component_units += units
            realised.append(
                RealisedMatch(
                    sell_id,
                    match.source_buy_transaction_id,
                    match.instrument_id,
                    match.matched_quantity,
                    proceeds.allocated(units, original_units),
                    match.removed_basis,
                )
            )
        unmatched_proceeds = None
        remainder = unmatched.get(sell_id)
        if remainder is not None:
            if remainder.instrument_id != fact.instrument_id:
                raise GrossRealisedPnlError("Component Instrument does not match SELL")
            units = _quantity_units(remainder.unmatched_quantity)
            component_units += units
            unmatched_proceeds = UnmatchedProceeds(
                sell_id,
                remainder.instrument_id,
                remainder.unmatched_quantity,
                proceeds.allocated(units, original_units),
            )
        if component_units != original_units:
            raise GrossRealisedPnlError("SELL quantity conservation failed")
        result = RealisedSell(
            sell_id,
            fact.instrument_id,
            fact.effective_date,
            proceeds,
            tuple(realised),
            unmatched_proceeds,
        )
        allocated = ExactMoney(Fraction(0), proceeds.currency_code)
        for item in result.matches:
            allocated = allocated + item.allocated_proceeds
        if result.unmatched_proceeds is not None:
            allocated = allocated + result.unmatched_proceeds.allocated_proceeds
        if allocated != proceeds:
            raise GrossRealisedPnlError("SELL proceeds conservation failed")
        if result.is_fully_resolved:
            pnl = ExactMoney(Fraction(0), proceeds.currency_code)
            basis = ExactMoney(Fraction(0), proceeds.currency_code)
            for item in result.matches:
                resolved_pnl = item.realised_pnl
                if resolved_pnl is None:
                    raise GrossRealisedPnlError("Resolved match lacks P&L")
                pnl = pnl + resolved_pnl
                basis = basis + item.removed_basis
            if pnl != proceeds - basis:
                raise GrossRealisedPnlError("Resolved SELL P&L conservation failed")
        sells.append(result)
    return GrossRealisedPnlReconstruction(fifo.account_id, tuple(sells))


def summarize_account_gross_realised_pnl(
    reconstruction: GrossRealisedPnlReconstruction,
) -> AccountGrossRealisedPnlSummary:
    resolved: dict[str, ExactMoney] = {}
    unresolved: list[UnresolvedComponent] = []
    for sell in reconstruction.sells:
        unresolved.extend(sell.unresolved_components)
        for match in sell.resolved_matches:
            money = match.realised_pnl
            if money is not None:
                currency = money.currency_code
                resolved[currency] = (
                    resolved.get(currency, ExactMoney(Fraction(0), currency)) + money
                )
    return AccountGrossRealisedPnlSummary(reconstruction.account_id, resolved, tuple(unresolved))


def aggregate_portfolio_gross_realised_pnl(
    summaries: Iterable[AccountGrossRealisedPnlSummary],
) -> PortfolioGrossRealisedPnlSummary:
    resolved: dict[str, ExactMoney] = {}
    unresolved: list[AccountUnresolvedComponent] = []
    for summary in summaries:
        for currency, money in summary.resolved_pnl_by_currency.items():
            resolved[currency] = resolved.get(currency, ExactMoney(Fraction(0), currency)) + money
        unresolved.extend(
            AccountUnresolvedComponent(summary.account_id, component)
            for component in summary.unresolved_components
        )
    return PortfolioGrossRealisedPnlSummary(resolved, tuple(unresolved))
