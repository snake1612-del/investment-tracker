from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Context, Decimal, localcontext
from types import TracebackType
from typing import cast

import pytest

from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    PortfolioRecord,
    TransactionRecord,
)
from app.application.use_cases import (
    NotFound,
    PositionDataIntegrityError,
    UowFactory,
    get_portfolio_positions,
)
from app.domain.transactions import TransactionType

NOW = datetime(2020, 1, 1, tzinfo=UTC)


def account(account_id: int, portfolio_id: int = 1) -> AccountRecord:
    return AccountRecord(account_id, portfolio_id, f"Account {account_id}", NOW, NOW)


def fact(
    account_id: int,
    instrument_id: int,
    transaction_type: TransactionType,
    quantity: str,
    *,
    effective_date: date = date(2020, 1, 1),
    settlement_date: date | None = None,
) -> TransactionRecord:
    return TransactionRecord(
        id=1,
        account_id=account_id,
        instrument_id=instrument_id,
        related_transaction_id=None,
        type=transaction_type,
        quantity=Decimal(quantity),
        price=Decimal("10"),
        cash_amount=Decimal("99"),
        currency_code="USD",
        effective_date=effective_date,
        settlement_date=settlement_date,
        note=None,
        created_at=NOW,
        updated_at=NOW,
    )


class FakePortfolios:
    def __init__(self, exists: bool) -> None:
        self.exists = exists

    def get(self, portfolio_id: int) -> PortfolioRecord | None:
        return PortfolioRecord(portfolio_id, "Main", "USD", NOW, NOW) if self.exists else None


class FakeAccounts:
    def __init__(self, records: list[AccountRecord]) -> None:
        self.records = records
        self.calls: list[int] = []

    def list_for_portfolio(self, portfolio_id: int) -> list[AccountRecord]:
        self.calls.append(portfolio_id)
        return [record for record in self.records if record.portfolio_id == portfolio_id]


class FakeTransactions:
    def __init__(self, by_account: dict[int, list[TransactionRecord]]) -> None:
        self.by_account = by_account
        self.calls: list[int] = []

    def list_for_account(self, account_id: int) -> list[TransactionRecord]:
        self.calls.append(account_id)
        return self.by_account.get(account_id, [])


class FakeInstruments:
    def __init__(self, names: dict[int, str]) -> None:
        self.names = names
        self.calls = 0

    def list(self) -> list[InstrumentRecord]:
        self.calls += 1
        return [InstrumentRecord(id_, name, NOW, NOW) for id_, name in self.names.items()]


class FakeUow:
    def __init__(
        self,
        accounts: list[AccountRecord],
        by_account: dict[int, list[TransactionRecord]],
        names: dict[int, str],
        *,
        portfolio_exists: bool = True,
    ) -> None:
        self.portfolios = FakePortfolios(portfolio_exists)
        self.accounts = FakeAccounts(accounts)
        self.transactions = FakeTransactions(by_account)
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


def test_missing_portfolio_stops_before_any_read_or_commit() -> None:
    fake = FakeUow([], {}, {}, portfolio_exists=False)
    with pytest.raises(NotFound):
        get_portfolio_positions(factory(fake), 99)
    assert fake.accounts.calls == fake.transactions.calls == []
    assert fake.instruments.calls == fake.commits == 0


@pytest.mark.parametrize("accounts", [[], [account(1), account(2)]])
def test_empty_portfolio_or_accounts_without_trades_return_empty(
    accounts: list[AccountRecord],
) -> None:
    fake = FakeUow(accounts, {}, {})
    assert get_portfolio_positions(factory(fake), 1) == []
    assert fake.accounts.calls == [1]
    assert fake.transactions.calls == [record.id for record in accounts]
    assert fake.instruments.calls == 1
    assert fake.commits == 0


@pytest.mark.parametrize(
    ("first_type", "first_quantity", "second_type", "second_quantity", "expected"),
    [
        (TransactionType.BUY, "10", TransactionType.SELL, "3", Decimal("7")),
        (TransactionType.BUY, "10", TransactionType.SELL, "10", None),
        (TransactionType.BUY, "3", TransactionType.SELL, "5", Decimal("-2")),
    ],
)
def test_positive_cancellation_and_negative_final_totals(
    first_type: TransactionType,
    first_quantity: str,
    second_type: TransactionType,
    second_quantity: str,
    expected: Decimal | None,
) -> None:
    fake = FakeUow(
        [account(1), account(2)],
        {
            1: [fact(1, 7, first_type, first_quantity)],
            2: [fact(2, 7, second_type, second_quantity)],
        },
        {7: "Share"},
    )
    result = get_portfolio_positions(factory(fake), 1)
    assert [(item.instrument_id, item.quantity) for item in result] == (
        [] if expected is None else [(7, expected)]
    )
    assert fake.transactions.calls == [1, 2]
    assert fake.instruments.calls == 1
    assert fake.commits == 0


def test_same_instrument_combines_accounts_before_final_filtering() -> None:
    fake = FakeUow(
        [account(1), account(2)],
        {
            1: [fact(1, 4, TransactionType.BUY, "10")],
            2: [
                fact(2, 4, TransactionType.BUY, "4"),
                fact(2, 4, TransactionType.SELL, "1"),
            ],
        },
        {4: "Share"},
    )
    assert [item.quantity for item in get_portfolio_positions(factory(fake), 1)] == [Decimal("13")]
    assert fake.commits == 0


def test_instrument_identity_dates_order_and_portfolio_isolation() -> None:
    fake = FakeUow(
        [account(1), account(2), account(3, portfolio_id=2)],
        {
            1: [
                fact(1, 2, TransactionType.BUY, "1", settlement_date=date(2099, 1, 1)),
                fact(1, 1, TransactionType.BUY, "2", effective_date=date(2019, 1, 1)),
            ],
            2: [
                fact(2, 1, TransactionType.BUY, "3"),
                fact(2, 1, TransactionType.BUY, "100", effective_date=date(9999, 1, 1)),
            ],
            3: [fact(3, 1, TransactionType.BUY, "1000")],
        },
        {2: "ABC", 1: "ABC"},
    )
    result = get_portfolio_positions(factory(fake), 1)
    assert [(item.instrument_id, item.instrument_name, item.quantity) for item in result] == [
        (1, "ABC", Decimal("5")),
        (2, "ABC", Decimal("1")),
    ]
    assert fake.accounts.calls == [1]
    assert fake.transactions.calls == [1, 2]
    assert fake.instruments.calls == 1
    assert fake.commits == 0


def test_cross_account_total_is_exact_with_one_domain_call_and_one_utc_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application import use_cases

    reconstruction_calls = 0
    clock_calls = 0
    original_reconstruct: Callable[..., dict[int, Decimal]] = use_cases.reconstruct_positions

    def counted_reconstruct(*args: object, **kwargs: object) -> dict[int, Decimal]:
        nonlocal reconstruction_calls
        reconstruction_calls += 1
        return original_reconstruct(*args, **kwargs)  # type: ignore[arg-type]

    class FixedDateTime:
        @staticmethod
        def now(timezone: object) -> datetime:
            nonlocal clock_calls
            assert timezone is UTC
            clock_calls += 1
            return datetime(2020, 1, 2, tzinfo=UTC)

    monkeypatch.setattr(use_cases, "reconstruct_positions", counted_reconstruct)
    monkeypatch.setattr(use_cases, "datetime", FixedDateTime)
    fake = FakeUow(
        [account(1), account(2)],
        {
            1: [fact(1, 1, TransactionType.BUY, "9999999999999999.999999999999")],
            2: [
                fact(2, 1, TransactionType.BUY, "9999999999999999.999999999999"),
                fact(2, 1, TransactionType.SELL, "0.000000000001"),
                fact(2, 1, TransactionType.BUY, "5", effective_date=date(2020, 1, 3)),
            ],
        },
        {1: "Share"},
    )
    with localcontext(Context(prec=3)):
        quantity = get_portfolio_positions(factory(fake), 1)[0].quantity
        assert quantity.as_tuple() == Decimal("19999999999999999.999999999997").as_tuple()
    assert reconstruction_calls == clock_calls == 1
    assert fake.instruments.calls == 1
    assert fake.commits == 0


def test_missing_instrument_metadata_is_internal_failure() -> None:
    fake = FakeUow([account(1)], {1: [fact(1, 42, TransactionType.BUY, "1")]}, {})
    with pytest.raises(PositionDataIntegrityError):
        get_portfolio_positions(factory(fake), 1)
    assert fake.instruments.calls == 1
    assert fake.commits == 0
