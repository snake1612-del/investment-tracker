"""F008 decimal-string wire representation, separate from F005 rational money."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.money import get_account_money_summary, get_portfolio_money_summary
from app.application.use_cases import UowFactory
from app.bootstrap import get_uow_factory
from app.domain.portfolio.engine.money import MONEY_FIELDS, CurrencyMoneySummary

router = APIRouter()
Factory = Annotated[UowFactory, Depends(get_uow_factory)]


def normalized_money(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


class CurrencyMoneyRead(BaseModel):
    currency_code: str
    cash_balance: str
    deposits: str
    withdrawals: str
    buy_trade_cash_outflow: str
    sell_trade_cash_inflow: str
    gross_dividend_income: str
    gross_coupon_income: str
    gross_investment_income: str
    fees_paid: str
    taxes_paid_or_withheld: str


class MoneySummaryRead(BaseModel):
    as_of_date: date
    currencies: list[CurrencyMoneyRead]


def _read(as_of_date: date, currencies: tuple[CurrencyMoneySummary, ...]) -> MoneySummaryRead:
    return MoneySummaryRead(
        as_of_date=as_of_date,
        currencies=[
            CurrencyMoneyRead(
                currency_code=item.currency_code,
                **{field: normalized_money(getattr(item, field)) for field in MONEY_FIELDS},
            )
            for item in currencies
        ],
    )


@router.get("/accounts/{account_id}/money-summary", response_model=MoneySummaryRead)
def account_money(account_id: int, as_of_date: date, factory: Factory) -> MoneySummaryRead:
    return _read(as_of_date, get_account_money_summary(factory, account_id, as_of_date))


@router.get("/portfolios/{portfolio_id}/money-summary", response_model=MoneySummaryRead)
def portfolio_money(portfolio_id: int, as_of_date: date, factory: Factory) -> MoneySummaryRead:
    return _read(as_of_date, get_portfolio_money_summary(factory, portfolio_id, as_of_date))
