from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from typing import cast

import pytest

from app.application.contracts import AccountRecord, InstrumentRecord, TransactionRecord
from app.application.use_cases import (
    NotFound,
    PositionDataIntegrityError,
    UowFactory,
    get_account_positions,
)
from app.domain.transactions import TransactionType

NOW = datetime(2020, 1, 1, tzinfo=UTC)


def trade(
    transaction_type: TransactionType,
    instrument_id: int,
    quantity: str,
    *,
    effective_date: date = date(2020, 1, 1),
) -> TransactionRecord:
    return TransactionRecord(
        id=1,
        account_id=1,
        instrument_id=instrument_id,
        related_transaction_id=None,
        type=transaction_type,
        quantity=Decimal(quantity),
        price=Decimal("10"),
        cash_amount=Decimal("99"),
        currency_code="USD",
        effective_date=effective_date,
        settlement_date=None,
        note=None,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeAccounts:
    def __init__(self, exists: bool) -> None:
        self.exists = exists

    def get(self, account_id: int) -> AccountRecord | None:
        return AccountRecord(account_id, 1, "Broker", NOW, NOW) if self.exists else None


class FakeTransactions:
    def __init__(self, records: list[TransactionRecord]) -> None:
        self.records = records
        self.calls = 0

    def list_for_account(self, account_id: int) -> list[TransactionRecord]:
        self.calls += 1
        return self.records


class FakeInstruments:
    def __init__(self, names: dict[int, str]) -> None:
        self.names = names
        self.list_calls = 0

    def list(self) -> list[InstrumentRecord]:
        self.list_calls += 1
        return [InstrumentRecord(id_, name, NOW, NOW) for id_, name in self.names.items()]


class FakeUow:
    def __init__(
        self,
        records: list[TransactionRecord],
        names: dict[int, str],
        *,
        account_exists: bool = True,
    ) -> None:
        self.accounts = FakeAccounts(account_exists)
        self.transactions = FakeTransactions(records)
        self.instruments = FakeInstruments(names)
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


def factory(fake: FakeUow) -> UowFactory:
    return cast(UowFactory, lambda: fake)


def test_missing_account_does_not_read_history_or_commit() -> None:
    fake = FakeUow([], {}, account_exists=False)
    with pytest.raises(NotFound):
        get_account_positions(factory(fake), 999)
    assert fake.transactions.calls == fake.instruments.list_calls == fake.commits == 0


def test_existing_empty_account_has_no_positions_and_no_commit() -> None:
    fake = FakeUow([], {})
    assert get_account_positions(factory(fake), 1) == []
    assert fake.transactions.calls == fake.instruments.list_calls == 1
    assert fake.commits == 0


def test_zero_omitted_negative_preserved_future_excluded_names_and_order() -> None:
    fake = FakeUow(
        [
            trade(TransactionType.BUY, 3, "5"),
            trade(TransactionType.SELL, 3, "5"),
            trade(TransactionType.SELL, 2, "4"),
            trade(TransactionType.BUY, 1, "1.000000000001"),
            trade(TransactionType.BUY, 1, "100", effective_date=date(9999, 1, 1)),
        ],
        {3: "Zero", 2: "Same", 1: "Same"},
    )
    result = get_account_positions(factory(fake), 1)
    assert [(item.instrument_id, item.instrument_name, item.quantity) for item in result] == [
        (1, "Same", Decimal("1.000000000001")),
        (2, "Same", Decimal("-4")),
    ]
    assert fake.transactions.calls == fake.instruments.list_calls == 1
    assert fake.commits == 0


def test_missing_metadata_is_internal_integrity_error_without_commit() -> None:
    fake = FakeUow([trade(TransactionType.BUY, 4, "1")], {})
    with pytest.raises(PositionDataIntegrityError):
        get_account_positions(factory(fake), 1)
    assert fake.instruments.list_calls == 1
    assert fake.commits == 0


def test_application_reads_current_utc_date_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    class FixedDateTime:
        @staticmethod
        def now(timezone: object) -> datetime:
            nonlocal calls
            assert timezone is UTC
            calls += 1
            return datetime(2020, 1, 2, 23, 59, tzinfo=UTC)

    monkeypatch.setattr("app.application.use_cases.datetime", FixedDateTime)
    fake = FakeUow(
        [
            trade(TransactionType.BUY, 1, "1", effective_date=date(2020, 1, 2)),
            trade(TransactionType.BUY, 1, "5", effective_date=date(2020, 1, 3)),
        ],
        {1: "Share"},
    )
    assert [item.quantity for item in get_account_positions(factory(fake), 1)] == [Decimal("1")]
    assert calls == 1
