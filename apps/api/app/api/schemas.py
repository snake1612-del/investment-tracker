"""HTTP-only request and response shapes for the persistence slice."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    PortfolioRecord,
    PositionRecord,
    TransactionRecord,
)


class PortfolioCreate(BaseModel):
    name: str
    base_currency: str


class PortfolioRead(BaseModel):
    id: int
    name: str
    base_currency: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: PortfolioRecord) -> PortfolioRead:
        return cls(**record.__dict__)


class AccountCreate(BaseModel):
    name: str


class AccountRead(BaseModel):
    id: int
    portfolio_id: int
    name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: AccountRecord) -> AccountRead:
        return cls(**record.__dict__)


class InstrumentCreate(BaseModel):
    name: str


class InstrumentRead(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: InstrumentRecord) -> InstrumentRead:
        return cls(**record.__dict__)


class DepositCreate(BaseModel):
    cash_amount: str
    currency_code: str
    effective_date: date
    note: str | None = None


class TradeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: int
    quantity: str
    price: str
    cash_amount: str
    currency_code: str
    effective_date: date
    settlement_date: date | None = None
    note: str | None = None


class TransactionRead(BaseModel):
    id: int
    account_id: int
    instrument_id: int | None
    related_transaction_id: int | None
    type: str
    quantity: str | None
    price: str | None
    cash_amount: str
    currency_code: str
    effective_date: date
    settlement_date: date | None
    note: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: TransactionRecord) -> TransactionRead:
        return cls(
            id=record.id,
            account_id=record.account_id,
            instrument_id=record.instrument_id,
            related_transaction_id=record.related_transaction_id,
            type=record.type.value,
            quantity=str(record.quantity) if record.quantity is not None else None,
            price=str(record.price) if record.price is not None else None,
            cash_amount=str(record.cash_amount),
            currency_code=record.currency_code,
            effective_date=record.effective_date,
            settlement_date=record.settlement_date,
            note=record.note,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class PositionRead(BaseModel):
    instrument_id: int
    instrument_name: str
    quantity: str

    @classmethod
    def from_record(cls, record: PositionRecord) -> PositionRead:
        return cls(
            instrument_id=record.instrument_id,
            instrument_name=record.instrument_name,
            quantity=str(record.quantity),
        )
