from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from typing import cast

import pytest

from app.application.contracts import AccountRecord, TransactionRecord
from app.application.use_cases import NotFound, UowFactory, create_deposit
from app.domain.transactions import CanonicalTransaction, InvalidTransaction


class FakeAccounts:
    def __init__(self, exists: bool) -> None:
        self.exists = exists

    def get(self, account_id: int) -> AccountRecord | None:
        now = datetime.now(UTC)
        return AccountRecord(account_id, 1, "Account", now, now) if self.exists else None


class FakeTransactions:
    def __init__(self) -> None:
        self.added: CanonicalTransaction | None = None

    def add(self, transaction: CanonicalTransaction) -> TransactionRecord:
        self.added = transaction
        now = datetime.now(UTC)
        return TransactionRecord(
            1,
            transaction.account_id,
            None,
            None,
            transaction.type,
            None,
            None,
            transaction.cash_amount,
            transaction.currency_code,
            transaction.effective_date,
            None,
            transaction.note,
            now,
            now,
        )


class FakeUow:
    def __init__(self, account_exists: bool) -> None:
        self.accounts = FakeAccounts(account_exists)
        self.transactions = FakeTransactions()
        self.commits = 0

    def __enter__(self) -> FakeUow:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1


def test_valid_deposit_persists_and_commits() -> None:
    fake = FakeUow(True)
    result = create_deposit(
        cast(UowFactory, lambda: fake), 1, Decimal("12.50"), "USD", date(2026, 9, 27)
    )
    assert result.cash_amount == Decimal("12.50")
    assert fake.transactions.added is not None
    assert fake.commits == 1


def test_missing_account_does_not_commit() -> None:
    fake = FakeUow(False)
    with pytest.raises(NotFound):
        create_deposit(cast(UowFactory, lambda: fake), 9, Decimal("1"), "USD", date.today())
    assert fake.commits == 0


def test_invalid_deposit_does_not_commit() -> None:
    fake = FakeUow(True)
    with pytest.raises(InvalidTransaction):
        create_deposit(cast(UowFactory, lambda: fake), 1, Decimal("0"), "USD", date.today())
    assert fake.transactions.added is None
    assert fake.commits == 0
