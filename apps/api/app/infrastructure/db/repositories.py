"""SQLAlchemy implementations of the current persistence capabilities."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.application.contracts import (
    AccountRecord,
    CsvImportRecord,
    InstrumentRecord,
    PortfolioRecord,
    TransactionRecord,
)
from app.application.use_cases import InvalidInput, NotFound
from app.domain.transactions import CanonicalTransaction, TransactionType
from app.infrastructure.db.models import (
    CsvImportModel,
    InstrumentModel,
    InvestmentAccountModel,
    PortfolioModel,
    TransactionModel,
)


def portfolio_record(model: PortfolioModel) -> PortfolioRecord:
    return PortfolioRecord(
        model.id, model.name, model.base_currency, model.created_at, model.updated_at
    )


def account_record(model: InvestmentAccountModel) -> AccountRecord:
    return AccountRecord(
        model.id, model.portfolio_id, model.name, model.created_at, model.updated_at
    )


def instrument_record(model: InstrumentModel) -> InstrumentRecord:
    return InstrumentRecord(model.id, model.name, model.created_at, model.updated_at)


def transaction_record(model: TransactionModel) -> TransactionRecord:
    return TransactionRecord(
        id=model.id,
        account_id=model.account_id,
        instrument_id=model.instrument_id,
        related_transaction_id=model.related_transaction_id,
        type=TransactionType(model.type),
        quantity=model.quantity,
        price=model.price,
        cash_amount=model.cash_amount,
        currency_code=model.currency_code,
        effective_date=model.effective_date,
        settlement_date=model.settlement_date,
        note=model.note,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str, base_currency: str) -> PortfolioRecord:
        model = PortfolioModel(name=name, base_currency=base_currency)
        self.session.add(model)
        self.session.flush()
        return portfolio_record(model)

    def get(self, portfolio_id: int) -> PortfolioRecord | None:
        model = self.session.get(PortfolioModel, portfolio_id)
        return portfolio_record(model) if model is not None else None

    def list(self) -> list[PortfolioRecord]:
        models = self.session.scalars(select(PortfolioModel).order_by(PortfolioModel.id)).all()
        return [portfolio_record(model) for model in models]


class SqlAlchemyInvestmentAccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, portfolio_id: int, name: str) -> AccountRecord:
        model = InvestmentAccountModel(portfolio_id=portfolio_id, name=name)
        self.session.add(model)
        self.session.flush()
        return account_record(model)

    def get(self, account_id: int) -> AccountRecord | None:
        model = self.session.get(InvestmentAccountModel, account_id)
        return account_record(model) if model is not None else None

    def list_for_portfolio(self, portfolio_id: int) -> list[AccountRecord]:
        models = self.session.scalars(
            select(InvestmentAccountModel)
            .where(InvestmentAccountModel.portfolio_id == portfolio_id)
            .order_by(InvestmentAccountModel.id)
        ).all()
        return [account_record(model) for model in models]


class SqlAlchemyInstrumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str) -> InstrumentRecord:
        model = InstrumentModel(name=name)
        self.session.add(model)
        self.session.flush()
        return instrument_record(model)

    def get(self, instrument_id: int) -> InstrumentRecord | None:
        model = self.session.get(InstrumentModel, instrument_id)
        return instrument_record(model) if model is not None else None

    def list(self) -> list[InstrumentRecord]:
        models = self.session.scalars(select(InstrumentModel).order_by(InstrumentModel.id)).all()
        return [instrument_record(model) for model in models]

    def existing_ids(self, instrument_ids: set[int]) -> set[int]:
        if not instrument_ids:
            return set()
        return set(
            self.session.scalars(
                select(InstrumentModel.id).where(InstrumentModel.id.in_(instrument_ids))
            )
        )


class SqlAlchemyCsvImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def record(model: CsvImportModel) -> CsvImportRecord:
        return CsvImportRecord(
            model.id,
            model.account_id,
            model.format_version,
            model.source_fingerprint,
            model.row_count,
            model.created_at,
        )

    def get(self, account_id: int, version: str, fingerprint: str) -> CsvImportRecord | None:
        model = self.session.scalar(
            select(CsvImportModel).where(
                CsvImportModel.account_id == account_id,
                CsvImportModel.format_version == version,
                CsvImportModel.source_fingerprint == fingerprint,
            )
        )
        return self.record(model) if model is not None else None

    def reserve(
        self, account_id: int, version: str, fingerprint: str, row_count: int
    ) -> CsvImportRecord | None:
        # Concurrent reservations wait for the winner's commit/rollback. Only the
        # winner inserts Transactions; unrelated conflicts must still fail.
        model = self.session.scalar(
            insert(CsvImportModel)
            .values(
                account_id=account_id,
                format_version=version,
                source_fingerprint=fingerprint,
                row_count=row_count,
            )
            .on_conflict_do_nothing(
                index_elements=["account_id", "format_version", "source_fingerprint"]
            )
            .returning(CsvImportModel)
        )
        return self.record(model) if model is not None else None


class SqlAlchemyTransactionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, transaction: CanonicalTransaction) -> TransactionRecord:
        model = TransactionModel(
            account_id=transaction.account_id,
            instrument_id=transaction.instrument_id,
            related_transaction_id=transaction.related_transaction_id,
            type=transaction.type.value,
            quantity=transaction.quantity,
            price=transaction.price,
            cash_amount=transaction.cash_amount,
            currency_code=transaction.currency_code,
            effective_date=transaction.effective_date,
            settlement_date=transaction.settlement_date,
            note=transaction.note,
        )
        self.session.add(model)
        self.session.flush()
        return transaction_record(model)

    def list_for_account(self, account_id: int) -> list[TransactionRecord]:
        models = self.session.scalars(
            select(TransactionModel)
            .where(TransactionModel.account_id == account_id)
            .order_by(TransactionModel.id)
        ).all()
        return [transaction_record(model) for model in models]

    def _scoped_model(self, account_id: int, transaction_id: int) -> TransactionModel | None:
        return self.session.scalar(
            select(TransactionModel).where(
                TransactionModel.id == transaction_id, TransactionModel.account_id == account_id
            )
        )

    def get_for_account(self, account_id: int, transaction_id: int) -> TransactionRecord | None:
        model = self._scoped_model(account_id, transaction_id)
        return transaction_record(model) if model is not None else None

    def update_facts(self, transaction_id: int, facts: CanonicalTransaction) -> TransactionRecord:
        model = self._scoped_model(facts.account_id, transaction_id)
        if model is None:
            raise NotFound("Transaction not found")
        if model.type != facts.type.value:
            raise InvalidInput("Transaction type cannot change")
        model.effective_date = facts.effective_date
        model.currency_code = facts.currency_code
        model.cash_amount = facts.cash_amount
        if facts.type in {TransactionType.BUY, TransactionType.SELL}:
            model.instrument_id = facts.instrument_id
            model.quantity = facts.quantity
            model.price = facts.price
            model.settlement_date = facts.settlement_date
        elif facts.type in {TransactionType.DIVIDEND, TransactionType.COUPON}:
            model.instrument_id = facts.instrument_id
        elif facts.type in {TransactionType.FEE, TransactionType.TAX}:
            model.instrument_id = facts.instrument_id
            model.related_transaction_id = facts.related_transaction_id
        # Identity, type, Account, creation metadata and note are untouched.
        model.updated_at = datetime.now(UTC)
        self.session.flush()
        return transaction_record(model)

    def delete_for_account(self, account_id: int, transaction_id: int) -> None:
        model = self._scoped_model(account_id, transaction_id)
        if model is None:
            raise NotFound("Transaction not found")
        self.session.delete(model)
        self.session.flush()

    def finalize_import_relation(self, transaction_id: int, parent_id: int) -> None:
        model = self.session.get(TransactionModel, transaction_id)
        if model is None:
            raise NotFound("Imported transaction not found")
        model.related_transaction_id = parent_id
        self.session.flush()
