"""Readable F004 reference histories; rational expectations are never rounded."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from fractions import Fraction

import pytest

from app.domain.portfolio.engine.fifo import (
    ExactMoney,
    FifoReconstructionError,
    LotTransactionFact,
    aggregate_portfolio_summaries,
    reconstruct_fifo_lots,
    summarize_account,
)
from app.domain.transactions import TransactionType


def buy(
    id_: int,
    quantity: str,
    cash: str,
    currency: str = "USD",
    day: int = 1,
    instrument: int = 1,
) -> LotTransactionFact:
    return LotTransactionFact(
        id_,
        1,
        TransactionType.BUY,
        instrument,
        Decimal(quantity),
        Decimal(cash),
        currency,
        date(2020, 1, day),
    )


def sell(id_: int, quantity: str, day: int = 2, instrument: int = 1) -> LotTransactionFact:
    return LotTransactionFact(
        id_,
        1,
        TransactionType.SELL,
        instrument,
        Decimal(quantity),
        None,
        None,
        date(2020, 1, day),
    )


@pytest.mark.parametrize(
    ("history", "remaining", "removed", "unmatched"),
    [
        pytest.param(
            [buy(1, "5", "500")], [(1, "5", Fraction(500), "USD")], [], [], id="one-open-lot"
        ),
        pytest.param(
            [buy(1, "5", "500"), sell(2, "2")],
            [(1, "3", Fraction(300), "USD")],
            [(2, 1, "2", Fraction(200), "USD")],
            [],
            id="partial-disposal",
        ),
        pytest.param(
            [buy(1, "5", "500"), buy(2, "5", "1000"), sell(3, "7")],
            [(1, "0", Fraction(0), "USD"), (2, "3", Fraction(600), "USD")],
            [(3, 1, "5", Fraction(500), "USD"), (3, 2, "2", Fraction(400), "USD")],
            [],
            id="fifo-two-lots",
        ),
        pytest.param(
            [buy(1, "0.3", "100"), sell(2, "0.1")],
            [(1, "0.2", Fraction(200, 3), "USD")],
            [(2, 1, "0.1", Fraction(100, 3), "USD")],
            [],
            id="fractional-quantity",
        ),
        pytest.param(
            [buy(1, "3", "100", "RUB"), sell(2, "1")],
            [(1, "2", Fraction(200, 3), "RUB")],
            [(2, 1, "1", Fraction(100, 3), "RUB")],
            [],
            id="exact-repeating-100-over-3",
        ),
        pytest.param(
            [buy(11, "4", "400"), sell(10, "4", day=1)],
            [(11, "4", Fraction(400), "USD")],
            [],
            [(10, "4")],
            id="same-date-sell-id-first-shuffled",
        ),
        pytest.param(
            [sell(11, "4", day=1), buy(10, "4", "400")],
            [(10, "0", Fraction(0), "USD")],
            [(11, 10, "4", Fraction(400), "USD")],
            [],
            id="same-date-buy-id-first-shuffled",
        ),
        pytest.param(
            [sell(1, "2", day=2), buy(2, "5", "500", day=1)],
            [(2, "3", Fraction(300), "USD")],
            [(1, 2, "2", Fraction(200), "USD")],
            [],
            id="backdated-buy",
        ),
        pytest.param(
            [buy(1, "5", "500", day=2), sell(2, "2", day=1)],
            [(1, "5", Fraction(500), "USD")],
            [],
            [(2, "2")],
            id="backdated-sell",
        ),
        pytest.param(
            [buy(1, "5", "500"), sell(2, "8")],
            [(1, "0", Fraction(0), "USD")],
            [(2, 1, "5", Fraction(500), "USD")],
            [(2, "3")],
            id="oversell",
        ),
        pytest.param([sell(1, "4")], [], [], [(1, "4")], id="sell-only"),
        pytest.param(
            [buy(1, "5", "500", instrument=1), sell(2, "4", instrument=2)],
            [(1, "5", Fraction(500), "USD")],
            [],
            [(2, "4")],
            id="instrument-id-isolation",
        ),
        pytest.param(
            [buy(1, "5", "500"), buy(2, "5", "45000", "RUB"), sell(3, "7")],
            [(1, "0", Fraction(0), "USD"), (2, "3", Fraction(27000), "RUB")],
            [(3, 1, "5", Fraction(500), "USD"), (3, 2, "2", Fraction(18000), "RUB")],
            [],
            id="mixed-basis-currencies",
        ),
        pytest.param(
            [buy(1, "3", "100"), sell(2, "1"), sell(3, "1"), sell(4, "1")],
            [(1, "0", Fraction(0), "USD")],
            [
                (2, 1, "1", Fraction(100, 3), "USD"),
                (3, 1, "1", Fraction(100, 3), "USD"),
                (4, 1, "1", Fraction(100, 3), "USD"),
            ],
            [],
            id="exact-full-disposal",
        ),
        pytest.param(
            [
                buy(1, "3", "100"),
                replace(sell(2, "1"), currency_code="RUB", cash_amount=Decimal("999")),
            ],
            [(1, "2", Fraction(200, 3), "USD")],
            [(2, 1, "1", Fraction(100, 3), "USD")],
            [],
            id="sell-currency-irrelevant",
        ),
    ],
)
def test_normative_fifo_cases(
    history: list[LotTransactionFact],
    remaining: list[tuple[int, str, Fraction, str]],
    removed: list[tuple[int, int, str, Fraction, str]],
    unmatched: list[tuple[int, str]],
) -> None:
    result = reconstruct_fifo_lots(history)
    assert [
        (
            lot.source_buy_transaction_id,
            lot.remaining_quantity,
            lot.remaining_basis.amount,
            lot.remaining_basis.currency_code,
        )
        for lot in result.lots
    ] == [(id_, Decimal(quantity), basis, currency) for id_, quantity, basis, currency in remaining]
    assert [
        (
            match.source_sell_transaction_id,
            match.source_buy_transaction_id,
            match.matched_quantity,
            match.removed_basis.amount,
            match.removed_basis.currency_code,
        )
        for match in result.disposal_matches
    ] == [
        (sell_id, buy_id, Decimal(quantity), basis, currency)
        for sell_id, buy_id, quantity, basis, currency in removed
    ]
    assert [
        (item.source_sell_transaction_id, item.unmatched_quantity)
        for item in result.unmatched_sells
    ] == [(id_, Decimal(quantity)) for id_, quantity in unmatched]
    assert result.is_fully_resolved == (not unmatched)


def test_account_isolation_and_portfolio_unresolved_sell_not_offset_by_other_long() -> None:
    first = reconstruct_fifo_lots([buy(1, "10", "1000")])
    second_fact = replace(sell(2, "3"), account_id=2)
    second = reconstruct_fifo_lots([second_fact])
    with pytest.raises(FifoReconstructionError):
        reconstruct_fifo_lots([buy(1, "10", "1000"), second_fact])
    summary = aggregate_portfolio_summaries([summarize_account(first), summarize_account(second)])[
        0
    ]
    assert summary.open_long_quantity == Decimal("10")
    assert summary.unmatched_sell_quantity == Decimal("3")
    assert summary.remaining_basis_by_currency == {"USD": ExactMoney(Fraction(1000), "USD")}
    assert not summary.is_fully_resolved


def test_linked_fee_and_tax_do_not_modify_basis() -> None:
    # LotTransactionFact deliberately has no relationship field: even linked fees
    # map to the same explicit no-lot-effect fact.
    fee = replace(buy(2, "1", "2"), type=TransactionType.FEE)
    tax = replace(fee, transaction_id=3, type=TransactionType.TAX)
    result = reconstruct_fifo_lots([buy(1, "1", "1000"), fee, tax])
    assert result.lots[0].original_basis == ExactMoney(Fraction(1000), "USD")
    assert result.lots[0].remaining_basis == result.lots[0].original_basis
