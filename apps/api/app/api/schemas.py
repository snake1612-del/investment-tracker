"""HTTP-only request and response shapes for the persistence slice."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    PortfolioRecord,
    PositionRecord,
    RealisedPnlReadRecord,
    TransactionRecord,
)
from app.domain.portfolio.engine.fifo import ExactMoney
from app.domain.portfolio.engine.realised_pnl import RealisedMatch


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


class DepositCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_date: date
    currency_code: str
    cash_amount: str


class TradeCorrectionRequest(DepositCorrectionRequest):
    instrument_id: int
    quantity: str
    price: str
    settlement_date: date | None


class WithdrawalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_amount: str
    currency_code: str
    effective_date: date
    note: str | None = None


class IncomeCreate(WithdrawalCreate):
    instrument_id: int


class ChargeCreate(WithdrawalCreate):
    instrument_id: int | None = None
    related_transaction_id: int | None = None


class IncomeCorrectionRequest(DepositCorrectionRequest):
    instrument_id: int


class ChargeCorrectionRequest(DepositCorrectionRequest):
    instrument_id: int | None
    related_transaction_id: int | None


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


class RationalAmountRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: Annotated[str, Field(strict=True, pattern=r"^(0|-?[1-9][0-9]*)$")]
    denominator: Annotated[str, Field(strict=True, pattern=r"^[1-9][0-9]*$")]


def _integer_to_decimal_string(value: int) -> str:
    """Exact local formatting; each conversion stays below Python's minimum digit limit."""
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    chunks: list[int] = []
    while magnitude:
        magnitude, remainder = divmod(magnitude, 10**9)
        chunks.append(remainder)
    return sign + str(chunks[-1]) + "".join(f"{chunk:09d}" for chunk in reversed(chunks[:-1]))


class ExactMoneyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency_code: str
    amount: RationalAmountRead

    @classmethod
    def from_money(cls, money: ExactMoney) -> ExactMoneyRead:
        # The exact value already has reduced terms, positive denominator and canonical zero.
        return cls(
            currency_code=money.currency_code,
            amount=RationalAmountRead(
                numerator=_integer_to_decimal_string(money.amount.numerator),
                denominator=_integer_to_decimal_string(money.amount.denominator),
            ),
        )


class UnresolvedPnlRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: int
    sell_transaction_id: int
    instrument_id: int
    instrument_name: str
    effective_date: date
    quantity: str
    allocated_proceeds: ExactMoneyRead


class CurrencyMismatchRead(UnresolvedPnlRead):
    reason: Literal["CURRENCY_MISMATCH"] = "CURRENCY_MISMATCH"
    removed_basis: ExactMoneyRead


class MissingAcquisitionBasisRead(UnresolvedPnlRead):
    reason: Literal["MISSING_ACQUISITION_BASIS"] = "MISSING_ACQUISITION_BASIS"


type UnresolvedPnlComponentRead = Annotated[
    CurrencyMismatchRead | MissingAcquisitionBasisRead, Field(discriminator="reason")
]


class RealisedPnlRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Literal["GROSS_TRADE_CASH_REALISED_PNL"] = "GROSS_TRADE_CASH_REALISED_PNL"
    resolved_pnl_by_currency: list[ExactMoneyRead]
    unresolved_components: list[UnresolvedPnlComponentRead]
    is_fully_resolved: bool

    @classmethod
    def from_record(cls, record: RealisedPnlReadRecord) -> RealisedPnlRead:
        unresolved: list[UnresolvedPnlComponentRead] = []
        for item in record.unresolved_components:
            component = item.component
            if isinstance(component, RealisedMatch):
                unresolved.append(
                    CurrencyMismatchRead(
                        account_id=item.account_id,
                        sell_transaction_id=component.source_sell_transaction_id,
                        instrument_id=component.instrument_id,
                        instrument_name=item.instrument_name,
                        effective_date=item.effective_date,
                        quantity=str(component.matched_quantity),
                        allocated_proceeds=ExactMoneyRead.from_money(component.allocated_proceeds),
                        removed_basis=ExactMoneyRead.from_money(component.removed_basis),
                    )
                )
            else:
                unresolved.append(
                    MissingAcquisitionBasisRead(
                        account_id=item.account_id,
                        sell_transaction_id=component.source_sell_transaction_id,
                        instrument_id=component.instrument_id,
                        instrument_name=item.instrument_name,
                        effective_date=item.effective_date,
                        quantity=str(component.unmatched_quantity),
                        allocated_proceeds=ExactMoneyRead.from_money(component.allocated_proceeds),
                    )
                )
        return cls(
            resolved_pnl_by_currency=[
                ExactMoneyRead.from_money(money) for money in record.resolved_pnl_by_currency
            ],
            unresolved_components=unresolved,
            is_fully_resolved=record.is_fully_resolved,
        )
