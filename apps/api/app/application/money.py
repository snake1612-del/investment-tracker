"""Account-first F008 read orchestration; canonical history is loaded once per Account."""

from datetime import date

from app.application.use_cases import NotFound, UowFactory, _canonical_from_record
from app.domain.portfolio.engine.money import (
    CurrencyMoneySummary,
    aggregate_money_summaries,
    reconstruct_money_summary,
)


def get_account_money_summary(
    factory: UowFactory,
    account_id: int,
    as_of_date: date,
) -> tuple[CurrencyMoneySummary, ...]:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        return reconstruct_money_summary(
            (
                _canonical_from_record(record)
                for record in uow.transactions.list_for_account(account_id)
            ),
            as_of_date,
        )


def get_portfolio_money_summary(
    factory: UowFactory,
    portfolio_id: int,
    as_of_date: date,
) -> tuple[CurrencyMoneySummary, ...]:
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        return aggregate_money_summaries(
            reconstruct_money_summary(
                (
                    _canonical_from_record(record)
                    for record in uow.transactions.list_for_account(account.id)
                ),
                as_of_date,
            )
            for account in uow.accounts.list_for_portfolio(portfolio_id)
        )
