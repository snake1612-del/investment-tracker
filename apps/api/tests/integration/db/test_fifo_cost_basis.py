from datetime import date
from decimal import Context, Decimal, localcontext
from fractions import Fraction

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.application.use_cases import (
    create_buy,
    create_instrument,
    create_investment_account,
    create_portfolio,
    create_sell,
    get_account_cost_basis,
    get_account_fifo,
    get_portfolio_cost_basis,
    list_account_transactions,
)
from app.domain.transactions import CanonicalTransaction, TransactionType
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.parametrize("buy_first", [True, False])
def test_real_same_date_persisted_id_tie_break(
    clean_db: sessionmaker[Session], buy_first: bool
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    instrument = create_instrument(factory, "Share")
    operations = [create_buy, create_sell] if buy_first else [create_sell, create_buy]
    records = [
        operation(
            factory,
            account.id,
            instrument.id,
            Decimal("3"),
            Decimal("999"),
            Decimal("100"),
            "USD",
            date(2020, 1, 1),
        )
        for operation in operations
    ]
    assert records[0].id < records[1].id
    result = get_account_fifo(factory, account.id)
    assert result.account_id == account.id
    assert result.lots[0].source_buy_transaction_id == records[0 if buy_first else 1].id
    if buy_first:
        assert result.is_fully_resolved
        assert result.lots[0].remaining_quantity == 0
        assert result.disposal_matches[0].source_sell_transaction_id == records[1].id
        assert result.disposal_matches[0].removed_basis.amount == Fraction(100)
    else:
        assert result.disposal_matches == ()
        assert result.unmatched_sells[0].source_sell_transaction_id == records[0].id
        assert result.unmatched_sells[0].unmatched_quantity == Decimal("3")
        assert result.lots[0].remaining_quantity == Decimal("3")


def test_persisted_backdating_mixed_currency_oversell_and_linked_fee(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    instrument = create_instrument(factory, "Share")
    sell = create_sell(
        factory,
        account.id,
        instrument.id,
        Decimal("7"),
        Decimal("10"),
        Decimal("70"),
        "EUR",
        date(2020, 1, 3),
    )
    usd = create_buy(
        factory,
        account.id,
        instrument.id,
        Decimal("5"),
        Decimal("999"),
        Decimal("500"),
        "USD",
        date(2020, 1, 1),
    )
    rub = create_buy(
        factory,
        account.id,
        instrument.id,
        Decimal("5"),
        Decimal("999"),
        Decimal("45000"),
        "RUB",
        date(2020, 1, 2),
    )
    assert sell.id < usd.id < rub.id
    with factory() as uow:
        uow.transactions.add(
            CanonicalTransaction(
                account_id=account.id,
                type=TransactionType.FEE,
                cash_amount=Decimal("2"),
                currency_code="USD",
                effective_date=date(2020, 1, 1),
                related_transaction_id=usd.id,
            )
        )
        uow.commit()
    result = get_account_fifo(factory, account.id)
    assert [match.removed_basis.amount for match in result.disposal_matches] == [
        Fraction(500),
        Fraction(18000),
    ]
    assert [match.removed_basis.currency_code for match in result.disposal_matches] == [
        "USD",
        "RUB",
    ]
    summary = get_account_cost_basis(factory, account.id)[0]
    assert summary.open_long_quantity == Decimal("3")
    assert summary.remaining_basis_by_currency["RUB"].amount == Fraction(27000)
    assert "USD" not in summary.remaining_basis_by_currency
    create_sell(
        factory,
        account.id,
        instrument.id,
        Decimal("4"),
        Decimal("1"),
        Decimal("1"),
        "USD",
        date(2020, 1, 4),
    )
    result = get_account_fifo(factory, account.id)
    assert result.unmatched_sells[0].unmatched_quantity == Decimal("1")
    assert all(lot.remaining_basis.amount == 0 for lot in result.lots)


def test_persisted_accounts_and_portfolios_do_not_cross_match(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    other_portfolio = create_portfolio(factory, "Other", "USD")
    long = create_investment_account(factory, portfolio.id, "Long")
    unresolved = create_investment_account(factory, portfolio.id, "Unresolved")
    create_investment_account(factory, portfolio.id, "Empty")
    foreign = create_investment_account(factory, other_portfolio.id, "Foreign")
    instrument = create_instrument(factory, "Share")
    create_buy(
        factory,
        long.id,
        instrument.id,
        Decimal("10"),
        Decimal("1"),
        Decimal("100"),
        "USD",
        date(2020, 1, 1),
    )
    create_sell(
        factory,
        unresolved.id,
        instrument.id,
        Decimal("3"),
        Decimal("1"),
        Decimal("3"),
        "USD",
        date(2020, 1, 2),
    )
    create_buy(
        factory,
        foreign.id,
        instrument.id,
        Decimal("999"),
        Decimal("1"),
        Decimal("999"),
        "USD",
        date(2020, 1, 1),
    )
    summary = get_portfolio_cost_basis(factory, portfolio.id)[0]
    assert summary.open_long_quantity == Decimal("10")
    assert summary.unmatched_sell_quantity == Decimal("3")
    assert not summary.is_fully_resolved
    assert summary.remaining_basis_by_currency["USD"].amount == Fraction(100)
    assert get_account_fifo(factory, unresolved.id).lots == ()


def test_canonical_precision_roundtrip_to_exact_rational_fifo(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    instrument = create_instrument(factory, "Share")
    buy = create_buy(
        factory,
        account.id,
        instrument.id,
        Decimal("3.000000000003"),
        Decimal("1"),
        Decimal("100.12345678"),
        "USD",
        date(2020, 1, 1),
    )
    create_sell(
        factory,
        account.id,
        instrument.id,
        Decimal("1.000000000001"),
        Decimal("1"),
        Decimal("1"),
        "RUB",
        date(2020, 1, 2),
    )
    records = list_account_transactions(factory, account.id)
    assert records[0].id == buy.id
    assert records[0].quantity == Decimal("3.000000000003")
    assert records[0].cash_amount == Decimal("100.12345678")
    with localcontext(Context(prec=3)):
        result = get_account_fifo(factory, account.id)
        assert result.lots[0].remaining_quantity == Decimal("2.000000000002")
        assert result.disposal_matches[0].removed_basis.amount == Fraction(10012345678, 300000000)
        assert result.lots[0].remaining_basis.amount == Fraction(20024691356, 300000000)
