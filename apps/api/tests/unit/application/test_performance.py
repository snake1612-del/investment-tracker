from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import cast
from unittest.mock import MagicMock, call

import pytest

from app.api.routes.performance import ratio
from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    MarketPriceRecord,
    TransactionRecord,
)
from app.application.performance import get_performance
from app.application.use_cases import InvalidInput, NotFound, UowFactory
from app.domain.transactions import TransactionType


def uow():
    now = datetime.now(UTC)
    unit = MagicMock()
    unit.__enter__.return_value = unit
    unit.instruments.list.return_value = [
        InstrumentRecord(i, f"Fund {i}", now, now) for i in (1, 2)
    ]
    unit.accounts.list_for_portfolio.return_value = [
        AccountRecord(i, 1, "Broker", now, now) for i in (2, 1)
    ]
    unit.transactions.list_for_account.side_effect = lambda account: [
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
            date(2020, 1, 1),
            None,
            None,
            now,
            now,
        )
    ]
    unit.market_prices.list_for_instruments.return_value = []
    return unit


def test_one_load_per_account_one_batch_even_for_long_period_no_commit():
    unit = uow()
    result = get_performance(
        cast(UowFactory, lambda: unit), 1, date(2020, 1, 2), date(2020, 12, 31), 2
    )
    unit.portfolios.get.assert_called_once_with(1)
    unit.accounts.list_for_portfolio.assert_called_once_with(1)
    assert unit.transactions.list_for_account.call_args_list == [call(1), call(2)]
    unit.market_prices.list_for_instruments.assert_called_once_with([1, 2])
    assert {item.account_id for item in result.result.performance.unresolved_components} == {1, 2}
    assert result.result.benchmark is not None
    unit.commit.assert_not_called()


@pytest.mark.parametrize("missing", ["portfolio", "benchmark"])
def test_missing_entities_do_not_load_histories(missing):
    unit = uow()
    if missing == "portfolio":
        unit.portfolios.get.return_value = None
    else:
        unit.instruments.get.return_value = None
    with pytest.raises(NotFound):
        get_performance(cast(UowFactory, lambda: unit), 1, date(2020, 1, 2), date(2020, 1, 3), 2)
    unit.transactions.list_for_account.assert_not_called()
    unit.market_prices.list_for_instruments.assert_not_called()


@pytest.mark.parametrize(
    "start,end", [(date.min, date(2020, 1, 2)), (date(2020, 1, 3), date(2020, 1, 2))]
)
def test_invalid_period_rejected_before_io(start, end):
    factory = MagicMock()
    with pytest.raises(InvalidInput):
        get_performance(factory, 1, start, end)
    factory.assert_not_called()


def test_account_first_offsets_do_not_create_public_account_endpoint():
    unit = uow()
    now = datetime.now(UTC)
    unit.market_prices.list_for_instruments.return_value = [
        MarketPriceRecord(1, 1, Decimal(10), "USD", date(2020, 1, 1), now, now)
    ]
    result = get_performance(cast(UowFactory, lambda: unit), 1, date(2020, 1, 2), date(2020, 1, 3))
    assert result.result.benchmark is None
    assert result.result.performance.twr is None  # exact zero offset Portfolio, no capital at risk


@pytest.mark.parametrize(
    "value", [Fraction(0), Fraction(-5, 7), Fraction(2), Fraction(10**5000 + 1, 10**5001 + 3)]
)
def test_exact_ratio_wire_arbitrary_precision(value):
    rendered = ratio(value)
    assert rendered is not None
    # Avoid Python's process-global decimal-string digit limit even in the test.
    from app.api.schemas import _integer_to_decimal_string

    assert rendered.numerator == _integer_to_decimal_string(value.numerator)
    assert rendered.denominator == _integer_to_decimal_string(value.denominator)
    assert rendered.model_dump_json().find('"numerator":"') >= 0
