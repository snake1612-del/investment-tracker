"""The concrete transaction boundary for persistence use cases."""

from types import TracebackType

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.application.contracts import (
    InstrumentRepository,
    InvestmentAccountRepository,
    PortfolioRepository,
    TransactionRepository,
)
from app.application.use_cases import PersistenceConflict
from app.infrastructure.db.repositories import (
    SqlAlchemyInstrumentRepository,
    SqlAlchemyInvestmentAccountRepository,
    SqlAlchemyPortfolioRepository,
    SqlAlchemyTransactionRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self.session_factory()
        self.portfolios: PortfolioRepository = SqlAlchemyPortfolioRepository(self.session)
        self.accounts: InvestmentAccountRepository = SqlAlchemyInvestmentAccountRepository(
            self.session
        )
        self.instruments: InstrumentRepository = SqlAlchemyInstrumentRepository(self.session)
        self.transactions: TransactionRepository = SqlAlchemyTransactionRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.session.rollback()
        finally:
            self.session.close()
        if isinstance(exc_value, IntegrityError):
            raise PersistenceConflict("Persistence constraint conflict") from exc_value

    def commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise PersistenceConflict("Persistence constraint conflict") from exc
