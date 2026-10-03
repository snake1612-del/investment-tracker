from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import MagicMock

import pytest

from app.application.contracts import TransactionRecord
from app.application.corrections import (
    DepositCorrection,
    TradeCorrection,
    delete_manual_transaction,
    update_manual_transaction,
)
from app.application.use_cases import NotFound, UowFactory
from app.domain.transactions import InvalidTransaction, TransactionType

DAY = date(2020, 1, 1)
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def uow(kind: TransactionType) -> MagicMock:
    fake = MagicMock()
    fake.__enter__.return_value = fake
    fake.transactions.get_for_account.return_value = TransactionRecord(
        7,
        1,
        2,
        None,
        kind,
        Decimal("2"),
        Decimal("10"),
        Decimal("19"),
        "USD",
        DAY,
        None,
        "Retain",
        NOW,
        NOW,
    )
    return fake


@pytest.mark.parametrize(
    "kind", [TransactionType.DEPOSIT, TransactionType.BUY, TransactionType.SELL]
)
def test_update_uses_existing_validation_and_commits_once(kind: TransactionType) -> None:
    fake = uow(kind)
    correction = (
        DepositCorrection(DAY, "EUR", Decimal("23"))
        if kind is TransactionType.DEPOSIT
        else TradeCorrection(3, DAY, "EUR", Decimal("3"), Decimal("7"), Decimal("23"), None)
    )
    result = update_manual_transaction(cast(UowFactory, lambda: fake), 1, 7, correction)
    fake.transactions.get_for_account.assert_called_once_with(1, 7)
    transaction_id, facts = fake.transactions.update_facts.call_args.args
    assert transaction_id == 7 and facts.type is kind
    assert facts.note == "Retain" and facts.cash_amount == Decimal("23")
    if kind is not TransactionType.DEPOSIT:
        assert facts.quantity == Decimal("3") and facts.price == Decimal("7")
        assert facts.instrument_id == 3
    assert result is fake.transactions.update_facts.return_value
    fake.commit.assert_called_once_with()
    fake.transactions.list_for_account.assert_not_called()


@pytest.mark.parametrize(
    "kind", [TransactionType.DEPOSIT, TransactionType.BUY, TransactionType.SELL]
)
def test_delete_only_removes_canonical_fact(kind: TransactionType) -> None:
    fake = uow(kind)
    delete_manual_transaction(cast(UowFactory, lambda: fake), 1, 7)
    fake.transactions.delete_for_account.assert_called_once_with(1, 7)
    fake.commit.assert_called_once_with()
    fake.transactions.list_for_account.assert_not_called()


@pytest.mark.parametrize(
    "kind", [TransactionType.DEPOSIT, TransactionType.BUY, TransactionType.SELL]
)
def test_invalid_update_never_mutates_or_commits(kind: TransactionType) -> None:
    fake = uow(kind)
    correction = (
        DepositCorrection(DAY, "USD", Decimal("0"))
        if kind is TransactionType.DEPOSIT
        else TradeCorrection(2, DAY, "USD", Decimal("0"), Decimal("1"), Decimal("1"), None)
    )
    with pytest.raises(InvalidTransaction):
        update_manual_transaction(cast(UowFactory, lambda: fake), 1, 7, correction)
    fake.transactions.update_facts.assert_not_called()
    fake.commit.assert_not_called()


@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize("missing", ["account", "transaction"])
def test_rejected_target_never_commits(operation: str, missing: str) -> None:
    fake = uow(TransactionType.BUY)
    if missing == "account":
        fake.accounts.get.return_value = None
    if missing == "transaction":
        fake.transactions.get_for_account.return_value = None
    with pytest.raises(NotFound):
        factory = cast(UowFactory, lambda: fake)
        if operation == "update":
            update_manual_transaction(
                factory,
                1,
                7,
                TradeCorrection(2, DAY, "USD", Decimal("1"), Decimal("1"), Decimal("1"), None),
            )
        else:
            delete_manual_transaction(factory, 1, 7)
    fake.transactions.update_facts.assert_not_called()
    fake.transactions.delete_for_account.assert_not_called()
    fake.commit.assert_not_called()
