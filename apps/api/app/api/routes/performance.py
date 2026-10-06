"""Portfolio-only F010/F011 transport: exact ratios, exact money, explicit diagnostics."""

from datetime import date
from fractions import Fraction
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.schemas import ExactMoneyRead, RationalAmountRead, _integer_to_decimal_string
from app.application.performance import get_performance
from app.application.use_cases import UowFactory
from app.bootstrap import get_uow_factory
from app.domain.portfolio.engine.exact import ExactMoney
from app.domain.portfolio.engine.performance import BenchmarkReason, Diagnostic, PerformanceReason

router = APIRouter()
Factory = Annotated[UowFactory, Depends(get_uow_factory)]


def ratio(value: Fraction | None) -> RationalAmountRead | None:
    return (
        RationalAmountRead(
            numerator=_integer_to_decimal_string(value.numerator),
            denominator=_integer_to_decimal_string(value.denominator),
        )
        if value is not None
        else None
    )


def money(value: ExactMoney | None) -> ExactMoneyRead | None:
    return ExactMoneyRead.from_money(value) if value is not None else None


class DiagnosticContextRead(BaseModel):
    date: date | None
    account_id: int | None
    instrument_id: int | None
    instrument_name: str | None
    currencies: tuple[str, ...]
    value: ExactMoneyRead | None
    capital_base: ExactMoneyRead | None

    @classmethod
    def from_fact(cls, fact: Diagnostic, names: dict[int, str]) -> DiagnosticContextRead:
        return cls(
            date=fact.date,
            account_id=fact.account_id,
            instrument_id=fact.instrument_id,
            instrument_name=names.get(fact.instrument_id)
            if fact.instrument_id is not None
            else None,
            currencies=fact.currencies,
            value=money(fact.value),
            capital_base=money(fact.capital_base),
        )


class PerformanceDiagnosticRead(DiagnosticContextRead):
    reason: PerformanceReason


class BenchmarkDiagnosticRead(DiagnosticContextRead):
    reason: BenchmarkReason


class PerformanceRead(BaseModel):
    currency_code: str | None
    opening_value: ExactMoneyRead | None
    closing_value: ExactMoneyRead | None
    twr: RationalAmountRead | None
    unresolved_components: list[PerformanceDiagnosticRead]
    is_fully_resolved: bool


class BenchmarkRead(BaseModel):
    instrument_id: int
    instrument_name: str
    currency_code: str | None
    opening_value: ExactMoneyRead | None
    ending_value: ExactMoneyRead | None
    benchmark_twr: RationalAmountRead | None
    active_return: RationalAmountRead | None
    ending_value_difference: ExactMoneyRead | None
    unresolved_components: list[BenchmarkDiagnosticRead]
    is_fully_resolved: bool


class PerformanceComparisonRead(BaseModel):
    start_date: date
    end_date: date
    performance: PerformanceRead
    benchmark: BenchmarkRead | None


@router.get("/portfolios/{portfolio_id}/performance")
def portfolio_performance(
    portfolio_id: int,
    start_date: date,
    end_date: date,
    factory: Factory,
    benchmark_instrument_id: int | None = None,
) -> PerformanceComparisonRead:
    record = get_performance(factory, portfolio_id, start_date, end_date, benchmark_instrument_id)
    item = record.result.performance
    benchmark = record.result.benchmark
    return PerformanceComparisonRead(
        start_date=start_date,
        end_date=end_date,
        performance=PerformanceRead(
            currency_code=item.currency_code,
            opening_value=money(item.opening_value),
            closing_value=money(item.closing_value),
            twr=ratio(item.twr),
            unresolved_components=[
                PerformanceDiagnosticRead(
                    reason=PerformanceReason(fact.reason.value),
                    **DiagnosticContextRead.from_fact(fact, record.instrument_names).model_dump(),
                )
                for fact in item.unresolved_components
            ],
            is_fully_resolved=item.is_fully_resolved,
        ),
        benchmark=BenchmarkRead(
            instrument_id=benchmark.instrument_id,
            instrument_name=record.instrument_names[benchmark.instrument_id],
            currency_code=benchmark.currency_code,
            opening_value=money(benchmark.opening_value),
            ending_value=money(benchmark.ending_value),
            benchmark_twr=ratio(benchmark.benchmark_twr),
            active_return=ratio(benchmark.active_return),
            ending_value_difference=money(benchmark.ending_value_difference),
            unresolved_components=[
                BenchmarkDiagnosticRead(
                    reason=BenchmarkReason(fact.reason.value),
                    **DiagnosticContextRead.from_fact(fact, record.instrument_names).model_dump(),
                )
                for fact in benchmark.unresolved_components
            ],
            is_fully_resolved=benchmark.is_fully_resolved,
        )
        if benchmark is not None
        else None,
    )
