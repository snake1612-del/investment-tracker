"""Small records and persistence capabilities used by the first use cases."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self

from app.domain.market_prices import MarketPrice
from app.domain.portfolio.engine.fifo import ExactMoney
from app.domain.portfolio.engine.realised_pnl import UnresolvedComponent
from app.domain.transactions import CanonicalTransaction, TransactionType


@dataclass(frozen=True)
class PortfolioRecord:
    id: int
    name: str
    base_currency: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AccountRecord:
    id: int
    portfolio_id: int
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class InstrumentRecord:
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PositionRecord:
    instrument_id: int
    instrument_name: str
    quantity: Decimal


@dataclass(frozen=True)
class UnresolvedPnlRecord:
    account_id: int
    instrument_name: str
    effective_date: date
    component: UnresolvedComponent


@dataclass(frozen=True)
class RealisedPnlReadRecord:
    resolved_pnl_by_currency: tuple[ExactMoney, ...]
    unresolved_components: tuple[UnresolvedPnlRecord, ...]

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_components


@dataclass(frozen=True)
class TransactionRecord:
    id: int
    account_id: int
    instrument_id: int | None
    related_transaction_id: int | None
    type: TransactionType
    quantity: Decimal | None
    price: Decimal | None
    cash_amount: Decimal
    currency_code: str
    effective_date: date
    settlement_date: date | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class PortfolioRepository(Protocol):
    def add(self, name: str, base_currency: str) -> PortfolioRecord: ...
    def get(self, portfolio_id: int) -> PortfolioRecord | None: ...
    def list(self) -> list[PortfolioRecord]: ...


@dataclass(frozen=True)
class MarketPriceRecord:
    id: int
    instrument_id: int
    price: Decimal
    currency_code: str
    effective_date: date
    created_at: datetime
    updated_at: datetime

    def fact(self) -> MarketPrice:
        return MarketPrice(self.instrument_id, self.price, self.currency_code, self.effective_date)


class MarketPriceObservationRepository(Protocol):
    def add(self, fact: MarketPrice) -> MarketPriceRecord: ...
    def get(self, instrument_id: int, observation_id: int) -> MarketPriceRecord | None: ...
    def list_for_instruments(self, instrument_ids: list[int]) -> list[MarketPriceRecord]: ...
    def update(self, observation_id: int, fact: MarketPrice) -> MarketPriceRecord: ...
    def delete(self, observation_id: int) -> None: ...


class InvestmentAccountRepository(Protocol):
    def add(self, portfolio_id: int, name: str) -> AccountRecord: ...
    def get(self, account_id: int) -> AccountRecord | None: ...
    def list_for_portfolio(self, portfolio_id: int) -> list[AccountRecord]: ...


class InstrumentRepository(Protocol):
    def add(self, name: str) -> InstrumentRecord: ...
    def get(self, instrument_id: int) -> InstrumentRecord | None: ...
    def list(self) -> list[InstrumentRecord]: ...


class TransactionRepository(Protocol):
    def add(self, transaction: CanonicalTransaction) -> TransactionRecord: ...
    def list_for_account(self, account_id: int) -> list[TransactionRecord]: ...
    def get_for_account(self, account_id: int, transaction_id: int) -> TransactionRecord | None: ...
    def update_facts(
        self, transaction_id: int, facts: CanonicalTransaction
    ) -> TransactionRecord: ...
    def delete_for_account(self, account_id: int, transaction_id: int) -> None: ...


class UnitOfWork(Protocol):
    market_prices: MarketPriceObservationRepository
    portfolios: PortfolioRepository
    accounts: InvestmentAccountRepository
    instruments: InstrumentRepository
    transactions: TransactionRepository

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
