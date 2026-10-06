"""One factual load per Account and one batch price load; no transport/SQL calculations."""

from dataclasses import dataclass
from datetime import date

from app.application.use_cases import InvalidInput, NotFound, UowFactory, _canonical_from_record
from app.domain.portfolio.engine.performance import PerformanceComparison, reconstruct_performance


@dataclass(frozen=True)
class PerformanceReadRecord:
    result: PerformanceComparison
    instrument_names: dict[int, str]


def get_performance(
    factory: UowFactory,
    portfolio_id: int,
    start_date: date,
    end_date: date,
    benchmark_instrument_id: int | None = None,
) -> PerformanceReadRecord:
    if start_date <= date.min or start_date > end_date:
        raise InvalidInput("Period requires an opening date and start_date <= end_date")
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        if (
            benchmark_instrument_id is not None
            and uow.instruments.get(benchmark_instrument_id) is None
        ):
            raise NotFound("Benchmark Instrument not found")
        accounts = sorted(uow.accounts.list_for_portfolio(portfolio_id), key=lambda item: item.id)
        histories = {
            account.id: tuple(
                map(_canonical_from_record, uow.transactions.list_for_account(account.id))
            )
            for account in accounts
        }
        ids = {
            fact.instrument_id
            for history in histories.values()
            for fact in history
            if fact.instrument_id is not None
        }
        if benchmark_instrument_id is not None:
            ids.add(benchmark_instrument_id)
        observations = uow.market_prices.list_for_instruments(sorted(ids))
        names = {item.id: item.name for item in uow.instruments.list()}
        if not ids <= names.keys():
            raise RuntimeError("Performance Instrument metadata is missing")
        return PerformanceReadRecord(
            reconstruct_performance(
                histories,
                (item.fact() for item in observations),
                start_date,
                end_date,
                benchmark_instrument_id,
            ),
            names,
        )
