"""The four canonical persistence entities from Decision 008."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class PortfolioModel(Base):
    __tablename__ = "portfolios"
    __table_args__ = (CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="base_currency_format"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvestmentAccountModel(Base):
    __tablename__ = "investment_accounts"
    __table_args__ = (Index(None, "portfolio_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("portfolios.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InstrumentModel(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('DEPOSIT', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'COUPON', 'FEE', 'TAX')",
            name="type_values",
        ),
        CheckConstraint("cash_amount >= 0", name="cash_amount_nonnegative"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="quantity_nonnegative"),
        CheckConstraint("price IS NULL OR price >= 0", name="price_nonnegative"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_format"),
        CheckConstraint(
            "related_transaction_id IS NULL OR related_transaction_id <> id",
            name="no_direct_self_reference",
        ),
        Index(None, "account_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("investment_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    instrument_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=True
    )
    related_transaction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CsvImportModel(Base):
    __tablename__ = "csv_imports"
    __table_args__ = (
        UniqueConstraint("account_id", "format_version", "source_fingerprint"),
        CheckConstraint("row_count > 0", name="row_count_positive"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("investment_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    format_version: Mapped[str] = mapped_column(String, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketPriceObservationModel(Base):
    __tablename__ = "market_price_observations"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_nonnegative"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_format"),
        UniqueConstraint("instrument_id", "effective_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
