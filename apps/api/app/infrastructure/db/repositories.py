"""SQLAlchemy implementations of the current persistence capabilities."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    PortfolioRecord,
    TransactionRecord,
)
from app.application.use_cases import InvalidInput, NotFound
from app.domain.transactions import CanonicalTransaction, TransactionType
from app.infrastructure.db.models import (
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
        # Identity, type, Account, creation metadata, note and canonical relations are untouched.
        self.session.flush()
        return transaction_record(model)

    def delete_for_account(self, account_id: int, transaction_id: int) -> None:
        model = self._scoped_model(account_id, transaction_id)
        if model is None:
            raise NotFound("Transaction not found")
        self.session.delete(model)
        self.session.flush()
