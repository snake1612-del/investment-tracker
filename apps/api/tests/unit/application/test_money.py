from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from app.application import money
from app.application.cash import (
    create_coupon,
    create_dividend,
    create_fee,
    create_tax,
    create_withdrawal,
)
from app.application.contracts import AccountRecord, TransactionRecord
from app.application.use_cases import NotFound, UowFactory
from app.domain.portfolio.engine.money import reconstruct_money_summary
from app.domain.transactions import TransactionType

DAY = date(2020, 1, 1)
NOW = datetime(2020, 1, 1, tzinfo=UTC)


def fake_uow() -> MagicMock:
    uow = MagicMock()
    uow.__enter__.return_value = uow
    return uow


@pytest.mark.parametrize("kind", ["withdrawal", "dividend", "coupon", "fee", "tax"])
def test_type_specific_create_validates_context_before_facts_and_commits_once(kind: str) -> None:
    uow = fake_uow()
    factory = cast(UowFactory, lambda: uow)
    constructors = {
        "withdrawal": create_withdrawal,
        "dividend": create_dividend,
        "coupon": create_coupon,
        "fee": create_fee,
        "tax": create_tax,
    }
    create = constructors[kind]
    if kind in {"dividend", "coupon"}:
        result = create(factory, 1, 2, Decimal("1"), "USD", DAY, "Note")
    else:
        result = create(factory, 1, Decimal("1"), "USD", DAY, note="Note")
    assert result is uow.transactions.add.return_value
    facts = uow.transactions.add.call_args.args[0]
    assert facts.type is TransactionType(kind.upper()) and facts.note == "Note"
    uow.accounts.get.assert_called_once_with(1)
    uow.commit.assert_called_once_with()
    uow.transactions.list_for_account.assert_not_called()


def test_missing_account_wins_before_constructor_validation() -> None:
    uow = fake_uow()
    uow.accounts.get.return_value = None
    with pytest.raises(NotFound):
        create_withdrawal(cast(UowFactory, lambda: uow), 1, Decimal("0"), "usd", DAY)
    uow.transactions.add.assert_not_called()
    uow.commit.assert_not_called()


def test_portfolio_reconstructs_each_account_before_aggregation_and_loads_once() -> None:
    uow = fake_uow()
    uow.accounts.list_for_portfolio.return_value = [
        AccountRecord(1, 3, "A", NOW, NOW),
        AccountRecord(2, 3, "B", NOW, NOW),
    ]
    record = TransactionRecord(
        7,
        1,
        None,
        None,
        TransactionType.DEPOSIT,
        None,
        None,
        Decimal("2"),
        "USD",
        DAY,
        None,
        None,
        NOW,
        NOW,
    )
    uow.transactions.list_for_account.side_effect = [[record], [replace(record, account_id=2)]]
    with patch.object(
        money, "reconstruct_money_summary", wraps=reconstruct_money_summary
    ) as reconstruct:
        (summary,) = money.get_portfolio_money_summary(cast(UowFactory, lambda: uow), 3, DAY)
    assert reconstruct.call_count == 2
    assert [call.args for call in uow.transactions.list_for_account.call_args_list] == [(1,), (2,)]
    assert summary.cash_balance == Decimal("4")
    uow.commit.assert_not_called()


def test_account_read_maps_all_facts_and_loads_only_its_history() -> None:
    uow = fake_uow()
    record = TransactionRecord(
        7,
        1,
        2,
        None,
        TransactionType.BUY,
        Decimal("1"),
        Decimal("999"),
        Decimal("2"),
        "USD",
        DAY,
        date(2030, 1, 1),
        None,
        NOW,
        NOW,
    )
    uow.transactions.list_for_account.return_value = [record]
    (summary,) = money.get_account_money_summary(cast(UowFactory, lambda: uow), 1, DAY)
    assert summary.cash_balance == Decimal("-2")
    uow.transactions.list_for_account.assert_called_once_with(1)
    uow.commit.assert_not_called()


@pytest.mark.parametrize("scope", ["account", "portfolio"])
def test_missing_read_scope_never_loads_history(scope: str) -> None:
    uow = fake_uow()
    uow.accounts.get.return_value = uow.portfolios.get.return_value = None
    operation = (
        money.get_account_money_summary if scope == "account" else money.get_portfolio_money_summary
    )
    with pytest.raises(NotFound):
        operation(cast(UowFactory, lambda: uow), 999, DAY)
    uow.transactions.list_for_account.assert_not_called()
