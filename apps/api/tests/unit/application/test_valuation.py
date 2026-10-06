from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import MagicMock, call

from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    MarketPriceRecord,
    TransactionRecord,
)
from app.application.use_cases import UowFactory
from app.application.valuation import get_valuation
from app.domain.transactions import TransactionType


def test_portfolio_loads_history_once_per_account_and_batch_prices_without_commit():
    now = datetime.now(UTC)
    day = date(2020, 1, 1)
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.accounts.list_for_portfolio.return_value = [
        AccountRecord(id_, 1, "Broker", now, now) for id_ in [1, 2]
    ]
    uow.instruments.list.return_value = [InstrumentRecord(1, "Fund", now, now)]
    uow.transactions.list_for_account.side_effect = lambda account: [
        TransactionRecord(
            account,
            account,
            1,
            None,
            TransactionType.BUY if account == 1 else TransactionType.SELL,
            Decimal(1),
            Decimal(99),
            Decimal(5),
            "USD",
            day,
            None,
            None,
            now,
            now,
        )
    ]
    uow.market_prices.list_for_instruments.return_value = [
        MarketPriceRecord(1, 1, Decimal(10), "USD", day, now, now)
    ]
    result = get_valuation(cast(UowFactory, lambda: uow), 1, day, portfolio=True).result
    assert not result.is_fully_resolved
    assert result.resolved_market_value_by_currency[0].amount == 0
    assert result.resolved_unrealised_pnl_by_currency[0].amount == 5
    assert uow.transactions.list_for_account.call_args_list == [call(1), call(2)]
    assert uow.market_prices.list_for_instruments.call_args_list == [call([1]), call([1])]
    uow.commit.assert_not_called()
