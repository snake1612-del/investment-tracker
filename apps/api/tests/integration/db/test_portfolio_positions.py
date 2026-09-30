from sqlalchemy.orm import Session, sessionmaker

from app.application.use_cases import create_investment_account, create_portfolio
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def test_account_repository_lists_only_requested_portfolio_in_id_order(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    requested = create_portfolio(factory, "Requested", "USD")
    other = create_portfolio(factory, "Other", "USD")
    empty = create_portfolio(factory, "Empty", "USD")
    first = create_investment_account(factory, requested.id, "First")
    excluded = create_investment_account(factory, other.id, "Other account")
    second = create_investment_account(factory, requested.id, "Second")

    with factory() as uow:
        assert uow.accounts.list_for_portfolio(requested.id) == [first, second]
        assert uow.accounts.list_for_portfolio(other.id) == [excluded]
        assert uow.accounts.list_for_portfolio(empty.id) == []
