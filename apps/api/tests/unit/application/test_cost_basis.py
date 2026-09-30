from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from types import SimpleNamespace, TracebackType
from typing import cast

import pytest

from app.application import use_cases
from app.application.contracts import AccountRecord, PortfolioRecord, TransactionRecord
from app.application.use_cases import (
    NotFound,
    UowFactory,
    get_account_cost_basis,
    get_account_fifo,
    get_portfolio_cost_basis,
)
from app.domain.portfolio.engine.fifo import (
    FifoReconstruction,
    FifoReconstructionError,
    LotTransactionFact,
)
from app.domain.transactions import TransactionType

NOW = datetime(2020, 1, 1, tzinfo=UTC)


def record(id_: int, account: int, type_: TransactionType, quantity: str) -> TransactionRecord:
    return TransactionRecord(
        id_,
        account,
        1,
        None,
        type_,
        Decimal(quantity),
        Decimal("999"),
        Decimal("100"),
        "USD",
        date(2020, 1, 1),
        date(2099, 1, 1),
        "ignored",
        NOW,
        NOW,
    )


class FakeUow:
    def __init__(self, histories: dict[int, list[TransactionRecord]], exists: bool = True) -> None:
        self.histories = histories
        self.reads: list[int] = []
        self.commits = 0
        self.accounts = SimpleNamespace(
            get=lambda id_: AccountRecord(id_, 1, "Account", NOW, NOW) if exists else None,
            list_for_portfolio=lambda id_: [
                AccountRecord(account_id, 1, "Account", NOW, NOW) for account_id in histories
            ],
        )
        self.portfolios = SimpleNamespace(
            get=lambda id_: PortfolioRecord(id_, "Portfolio", "USD", NOW, NOW) if exists else None
        )
        self.transactions = SimpleNamespace(list_for_account=self.list_for_account)

    def list_for_account(self, account_id: int) -> list[TransactionRecord]:
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
    "capability", [get_account_fifo, get_account_cost_basis, get_portfolio_cost_basis]
)
def test_missing_entity_does_not_read_history_or_commit(
    capability: Callable[[UowFactory, int], object],
) -> None:
    fake = FakeUow({}, exists=False)
    with pytest.raises(NotFound):
        capability(factory(fake), 9)
    assert fake.reads == []
    assert fake.commits == 0


def test_empty_account_identity_and_empty_summaries() -> None:
    fake = FakeUow({1: []})
    result = get_account_fifo(factory(fake), 1)
    assert result.account_id == 1
    assert result.is_fully_resolved
    assert get_account_cost_basis(factory(fake), 1) == ()
    assert get_portfolio_cost_basis(factory(fake), 1) == ()
    assert get_portfolio_cost_basis(factory(FakeUow({})), 1) == ()
    assert fake.commits == 0


def test_explicit_domain_mapping_and_once_per_account_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeUow(
        {
            1: [record(10, 1, TransactionType.BUY, "10")],
            2: [record(11, 2, TransactionType.SELL, "3")],
        }
    )
    original = use_cases.reconstruct_fifo_lots
    calls: list[tuple[int | None, list[LotTransactionFact]]] = []

    def observed(
        facts: Iterable[LotTransactionFact], *, account_id: int | None = None
    ) -> FifoReconstruction:
        mapped = list(facts)
        assert all(type(item) is LotTransactionFact for item in mapped)
        calls.append((account_id, mapped))
        return original(mapped, account_id=account_id)

    monkeypatch.setattr(use_cases, "reconstruct_fifo_lots", observed)
    with localcontext(Context(prec=3)):
        summary = get_portfolio_cost_basis(factory(fake), 1)[0]
    assert summary.open_long_quantity == Decimal("10")
    assert summary.unmatched_sell_quantity == Decimal("3")
    assert not summary.is_fully_resolved
    assert summary.remaining_basis_by_currency["USD"].amount == Fraction(100)
    assert fake.reads == [1, 2]
    assert [account for account, _ in calls] == [1, 2]
    assert calls[0][1][0].transaction_id == 10
    assert calls[0][1][0].cash_amount == Decimal("100")
    assert fake.commits == 0


def test_history_account_contamination_fails_instead_of_reconstructing_other_account() -> None:
    fake = FakeUow({1: [record(1, 2, TransactionType.BUY, "3")]})
    with pytest.raises(FifoReconstructionError):
        get_account_fifo(factory(fake), 1)
    assert fake.commits == 0
