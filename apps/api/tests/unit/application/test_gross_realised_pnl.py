from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace, TracebackType
from typing import cast

import pytest

from app.application import use_cases
from app.application.contracts import AccountRecord, TransactionRecord
from app.application.use_cases import (
    NotFound,
    UowFactory,
    get_account_gross_realised_pnl,
    get_account_gross_realised_pnl_summary,
    get_portfolio_gross_realised_pnl_summary,
)
from app.domain.portfolio.engine.fifo import FifoReconstruction, LotTransactionFact
from app.domain.portfolio.engine.realised_pnl import GrossRealisedPnlReconstruction
from app.domain.transactions import TransactionType

NOW = datetime(2020, 1, 1, tzinfo=UTC)


def record(id_: int, account_id: int, type_: TransactionType) -> TransactionRecord:
    return TransactionRecord(
        id_,
        account_id,
        1,
        None,
        type_,
        Decimal("3"),
        Decimal("999"),
        Decimal("100" if type_ is TransactionType.BUY else "150"),
        "USD",
        date(2020, 1, 1),
        date(2099, 1, 1),
        None,
        NOW,
        NOW,
    )


class FakeUow:
    def __init__(self, histories: dict[int, list[TransactionRecord]], exists: bool = True) -> None:
        self.histories = histories
        self.reads: list[int] = []
        self.commits = 0
        self.accounts = SimpleNamespace(
            get=lambda id_: AccountRecord(id_, 1, "Broker", NOW, NOW) if exists else None,
            list_for_portfolio=lambda id_: [
                AccountRecord(id_, 1, "Broker", NOW, NOW) for id_ in histories
            ],
        )
        self.portfolios = SimpleNamespace(get=lambda id_: object() if exists else None)
        self.transactions = SimpleNamespace(list_for_account=self.read)

    def read(self, account_id: int) -> list[TransactionRecord]:
        self.reads.append(account_id)
        return self.histories.get(account_id, [])

    def __enter__(self) -> FakeUow:
        return self

    def __exit__(
        self,
        type_: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1


def factory(fake: FakeUow) -> UowFactory:
    return cast(UowFactory, lambda: fake)


@pytest.mark.parametrize(
    "capability",
    [
        get_account_gross_realised_pnl,
        get_account_gross_realised_pnl_summary,
        get_portfolio_gross_realised_pnl_summary,
    ],
)
def test_missing_entity_stops_without_history_load_or_commit(
    capability: Callable[[UowFactory, int], object],
) -> None:
    fake = FakeUow({}, exists=False)
    with pytest.raises(NotFound):
        capability(factory(fake), 1)
    assert fake.reads == []
    assert fake.commits == 0


def test_account_empty_history_preserves_identity_and_completeness() -> None:
    fake = FakeUow({})
    result = get_account_gross_realised_pnl(factory(fake), 7)
    assert result.account_id == 7 and result.sells == ()
    assert get_account_gross_realised_pnl_summary(factory(fake), 7).is_fully_resolved
    assert get_portfolio_gross_realised_pnl_summary(factory(fake), 1).is_fully_resolved
    assert fake.commits == 0


@pytest.mark.parametrize("portfolio", [False, True])
def test_history_and_mapping_once_fifo_once_f005_once_same_tuple(
    monkeypatch: pytest.MonkeyPatch,
    portfolio: bool,
) -> None:
    fake = FakeUow({1: [record(1, 1, TransactionType.BUY), record(2, 1, TransactionType.SELL)]})
    if portfolio:
        fake.histories[2] = [record(3, 2, TransactionType.SELL)]
    mapping_calls: list[int] = []
    fifo_calls: dict[int | None, tuple[LotTransactionFact, ...]] = {}
    pnl_calls: list[int | None] = []
    original_mapping = use_cases._lot_fact_from_record
    original_fifo = use_cases.reconstruct_fifo_lots
    original_pnl = use_cases.reconstruct_gross_realised_pnl

    def mapped(record: TransactionRecord) -> LotTransactionFact:
        mapping_calls.append(record.id)
        return original_mapping(record)

    def fifo(
        facts: Iterable[LotTransactionFact], *, account_id: int | None = None
    ) -> FifoReconstruction:
        assert type(facts) is tuple
        assert account_id not in fifo_calls
        fifo_calls[account_id] = cast(tuple[LotTransactionFact, ...], facts)
        return original_fifo(facts, account_id=account_id)

    def pnl(
        fifo: FifoReconstruction, facts: Iterable[LotTransactionFact]
    ) -> GrossRealisedPnlReconstruction:
        assert facts is fifo_calls[fifo.account_id]
        pnl_calls.append(fifo.account_id)
        return original_pnl(fifo, facts)

    monkeypatch.setattr(use_cases, "_lot_fact_from_record", mapped)
    monkeypatch.setattr(use_cases, "reconstruct_fifo_lots", fifo)
    monkeypatch.setattr(use_cases, "reconstruct_gross_realised_pnl", pnl)
    if portfolio:
        result = get_portfolio_gross_realised_pnl_summary(factory(fake), 1)
        assert not result.is_fully_resolved
        assert result.unresolved_components[0].account_id == 2
        assert result.unresolved_components[0].component.source_sell_transaction_id == 3
    else:
        result = get_account_gross_realised_pnl_summary(factory(fake), 1)
        assert result.is_fully_resolved
    assert result.resolved_pnl_by_currency["USD"].amount == Fraction(50)
    expected = [1, 2] if portfolio else [1]
    assert fake.reads == pnl_calls == expected
    assert mapping_calls == ([1, 2, 3] if portfolio else [1, 2])
    assert fake.commits == 0
