"""Small records and persistence capabilities used by the first use cases."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self

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


class InvestmentAccountRepository(Protocol):
    def add(self, portfolio_id: int, name: str) -> AccountRecord: ...
    def get(self, account_id: int) -> AccountRecord | None: ...


class InstrumentRepository(Protocol):
    def add(self, name: str) -> InstrumentRecord: ...
    def get(self, instrument_id: int) -> InstrumentRecord | None: ...
    def list(self) -> list[InstrumentRecord]: ...


class TransactionRepository(Protocol):
    def add(self, transaction: CanonicalTransaction) -> TransactionRecord: ...
    def list_for_account(self, account_id: int) -> list[TransactionRecord]: ...


class UnitOfWork(Protocol):
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
