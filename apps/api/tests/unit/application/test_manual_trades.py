from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from typing import cast

import pytest

from app.application.contracts import AccountRecord, InstrumentRecord, TransactionRecord
from app.application.use_cases import (
    NotFound,
    UowFactory,
    create_buy,
    create_instrument,
    create_sell,
    list_instruments,
)
from app.domain.instruments import InvalidInstrument
from app.domain.transactions import CanonicalTransaction, InvalidTransaction, TransactionType

NOW = datetime(2026, 9, 29, tzinfo=UTC)
TRADE_DATE = date(2020, 1, 2)


class FakeAccounts:
    def __init__(self, exists: bool) -> None:
        self.exists = exists

    def get(self, account_id: int) -> AccountRecord | None:
        return AccountRecord(account_id, 1, "Account", NOW, NOW) if self.exists else None


class FakeInstruments:
    def __init__(self, exists: bool) -> None:
        self.exists = exists
        self.records: list[InstrumentRecord] = []

    def add(self, name: str) -> InstrumentRecord:
        record = InstrumentRecord(len(self.records) + 1, name, NOW, NOW)
        self.records.append(record)
        return record

    def get(self, instrument_id: int) -> InstrumentRecord | None:
        return InstrumentRecord(instrument_id, "Share", NOW, NOW) if self.exists else None

    def list(self) -> list[InstrumentRecord]:
        return self.records


class FakeTransactions:
    def __init__(self) -> None:
        self.added: CanonicalTransaction | None = None

    def add(self, transaction: CanonicalTransaction) -> TransactionRecord:
        self.added = transaction
        return TransactionRecord(
            1,
            transaction.account_id,
            transaction.instrument_id,
            transaction.related_transaction_id,
            transaction.type,
            transaction.quantity,
            transaction.price,
            transaction.cash_amount,
            transaction.currency_code,
            transaction.effective_date,
            transaction.settlement_date,
            transaction.note,
            NOW,
            NOW,
        )


class FakeUow:
    def __init__(self, account_exists: bool = True, instrument_exists: bool = True) -> None:
        self.accounts = FakeAccounts(account_exists)
        self.instruments = FakeInstruments(instrument_exists)
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


def create_trade(factory: UowFactory, trade_type: TransactionType) -> TransactionRecord:
    use_case = create_buy if trade_type is TransactionType.BUY else create_sell
    return use_case(factory, 1, 2, Decimal("2"), Decimal("10"), Decimal("19.99"), "USD", TRADE_DATE)


def test_create_instrument_trims_and_commits_once() -> None:
    fake = FakeUow()
    result = create_instrument(cast(UowFactory, lambda: fake), "  Акция  ")
    assert result.name == "Акция"
    assert fake.commits == 1


def test_duplicate_instrument_names_are_allowed_and_listed() -> None:
    fake = FakeUow()
    factory = cast(UowFactory, lambda: fake)
    first = create_instrument(factory, "Same")
    second = create_instrument(factory, "Same")
    assert first.id != second.id
    assert [record.name for record in list_instruments(factory)] == ["Same", "Same"]
    assert fake.commits == 2


@pytest.mark.parametrize("name", ["  ", "x" * 201])
def test_invalid_instrument_does_not_commit(name: str) -> None:
    fake = FakeUow()
    with pytest.raises(InvalidInstrument):
        create_instrument(cast(UowFactory, lambda: fake), name)
    assert fake.commits == 0


@pytest.mark.parametrize("trade_type", [TransactionType.BUY, TransactionType.SELL])
def test_create_manual_trade_commits_once_and_preserves_facts(
    trade_type: TransactionType,
) -> None:
    fake = FakeUow()
    result = create_trade(cast(UowFactory, lambda: fake), trade_type)
    assert fake.commits == 1
    assert fake.transactions.added is not None
    assert result.type is trade_type
    assert result.instrument_id == 2
    assert result.related_transaction_id is None
    assert result.cash_amount == Decimal("19.99")
    assert result.quantity == Decimal("2")
    assert result.price == Decimal("10")


@pytest.mark.parametrize("trade_type", [TransactionType.BUY, TransactionType.SELL])
@pytest.mark.parametrize(("account_exists", "instrument_exists"), [(False, True), (True, False)])
def test_missing_reference_does_not_commit(
    trade_type: TransactionType, account_exists: bool, instrument_exists: bool
) -> None:
    fake = FakeUow(account_exists, instrument_exists)
    with pytest.raises(NotFound):
        create_trade(cast(UowFactory, lambda: fake), trade_type)
    assert fake.transactions.added is None
    assert fake.commits == 0


@pytest.mark.parametrize("trade_type", [TransactionType.BUY, TransactionType.SELL])
def test_invalid_manual_trade_does_not_commit(trade_type: TransactionType) -> None:
    fake = FakeUow()
    use_case = create_buy if trade_type is TransactionType.BUY else create_sell
    with pytest.raises(InvalidTransaction):
        use_case(
            cast(UowFactory, lambda: fake),
            1,
            2,
            Decimal("0"),
            Decimal("10"),
            Decimal("20"),
            "USD",
            TRADE_DATE,
        )
    assert fake.transactions.added is None
    assert fake.commits == 0
