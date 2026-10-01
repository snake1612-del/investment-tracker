from datetime import date
from decimal import Context, Decimal, localcontext
from fractions import Fraction

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.application.use_cases import (
    create_buy,
    create_instrument,
    create_investment_account,
    create_portfolio,
    create_sell,
    get_account_gross_realised_pnl,
    get_account_gross_realised_pnl_summary,
    get_portfolio_gross_realised_pnl_summary,
)
from app.domain.portfolio.engine.fifo import ExactMoney
from app.domain.portfolio.engine.realised_pnl import RealisedPnlUnresolvedReason
from app.domain.transactions import CanonicalTransaction, TransactionType
from app.infrastructure.db.models import TransactionModel
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def test_cash_not_price_exact_roundtrip_and_settlement_ignored(
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
        Decimal("999"),
        Decimal("100.12345678"),
        "USD",
        date(2020, 1, 1),
    )
    sell = create_sell(
        factory,
        account.id,
        instrument.id,
        Decimal("1.000000000001"),
        Decimal("999"),
        Decimal("50.12345678"),
        "USD",
        date(2020, 1, 2),
        date(2099, 1, 1),
    )
    with localcontext(Context(prec=3)):
        result = get_account_gross_realised_pnl(factory, account.id)
        match = result.sells[0].matches[0]
        assert match.source_sell_transaction_id == sell.id
        assert match.source_buy_transaction_id == buy.id
        assert match.matched_quantity == Decimal("1.000000000001")
        assert match.allocated_proceeds == ExactMoney(Fraction(5012345678, 100000000), "USD")
        assert match.removed_basis.amount == Fraction(10012345678, 300000000)
        assert match.realised_pnl == ExactMoney(Fraction(5024691356, 300000000), "USD")
        assert result.sells[0].effective_date == date(2020, 1, 2)


@pytest.mark.parametrize("buy_first", [True, False])
def test_real_same_day_ids_control_fifo_and_pnl(
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
            Decimal("1"),
            Decimal("999"),
            Decimal("100" if operation is create_buy else "150"),
            "USD",
            date(2020, 1, 1),
        )
        for operation in operations
    ]
    assert records[0].id < records[1].id
    result = get_account_gross_realised_pnl(factory, account.id).sells[0]
    if buy_first:
        assert result.matches[0].realised_pnl == ExactMoney(Fraction(50), "USD")
        assert result.is_fully_resolved
    else:
        assert result.matches == () and not result.is_fully_resolved
        assert result.unmatched_proceeds is not None
        assert result.unmatched_proceeds.allocated_proceeds == ExactMoney(Fraction(150), "USD")


def test_oversell_and_currency_mismatch_preserve_all_components(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    account = create_investment_account(factory, portfolio.id, "Broker")
    instrument = create_instrument(factory, "Share")
    for cash, currency in [("20", "USD"), ("200", "RUB")]:
        create_buy(
            factory,
            account.id,
            instrument.id,
            Decimal("2"),
            Decimal("1"),
            Decimal(cash),
            currency,
            date(2020, 1, 1),
        )
    create_sell(
        factory,
        account.id,
        instrument.id,
        Decimal("6"),
        Decimal("1"),
        Decimal("150"),
        "USD",
        date(2020, 1, 2),
    )
    result = get_account_gross_realised_pnl(factory, account.id).sells[0]
    assert result.matches[0].realised_pnl == ExactMoney(Fraction(30), "USD")
    assert result.matches[1].realised_pnl is None
    assert result.matches[1].unresolved_reason is RealisedPnlUnresolvedReason.CURRENCY_MISMATCH
    assert result.matches[1].removed_basis == ExactMoney(Fraction(200), "RUB")
    assert result.unmatched_proceeds is not None
    assert result.unmatched_proceeds.allocated_proceeds == ExactMoney(Fraction(50), "USD")
    assert result.unmatched_proceeds.unmatched_quantity == Decimal("2")
    summary = get_account_gross_realised_pnl_summary(factory, account.id)
    assert summary.resolved_pnl_by_currency == {"USD": ExactMoney(Fraction(30), "USD")}
    assert len(summary.unresolved_components) == 2 and not summary.is_fully_resolved


def test_portfolio_account_isolation_and_currency_partitioning(
    clean_db: sessionmaker[Session],
) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(clean_db)

    portfolio = create_portfolio(factory, "Main", "USD")
    foreign = create_portfolio(factory, "Foreign", "USD")
    instrument = create_instrument(factory, "Share")
    for currency in ["USD", "RUB"]:
        account = create_investment_account(factory, portfolio.id, currency)
        create_buy(
            factory,
            account.id,
            instrument.id,
            Decimal("10"),
            Decimal("1"),
            Decimal("100"),
            currency,
            date(2020, 1, 1),
        )
        create_sell(
            factory,
            account.id,
            instrument.id,
            Decimal("5"),
            Decimal("1"),
            Decimal("75"),
            currency,
            date(2020, 1, 2),
        )
    missing = create_investment_account(factory, portfolio.id, "Missing basis")
    sell = create_sell(
        factory,
        missing.id,
        instrument.id,
        Decimal("3"),
        Decimal("1"),
        Decimal("45"),
        "USD",
        date(2020, 1, 3),
    )
    other = create_investment_account(factory, foreign.id, "Foreign")
    create_sell(
        factory,
        other.id,
        instrument.id,
        Decimal("999"),
        Decimal("1"),
        Decimal("999"),
        "USD",
        date(2020, 1, 1),
    )
    summary = get_portfolio_gross_realised_pnl_summary(factory, portfolio.id)
    assert summary.resolved_pnl_by_currency == {
        "USD": ExactMoney(Fraction(25), "USD"),
        "RUB": ExactMoney(Fraction(25), "RUB"),
    }
    assert len(summary.unresolved_components) == 1
    assert summary.unresolved_components[0].account_id == missing.id
    assert summary.unresolved_components[0].component.source_sell_transaction_id == sell.id
    assert not summary.is_fully_resolved


def test_backdated_recomputation_and_linked_fee_tax_exclusion(
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
        Decimal("5"),
        Decimal("1"),
        Decimal("50"),
        "USD",
        date(2020, 1, 2),
    )
    sell = create_sell(
        factory,
        account.id,
        instrument.id,
        Decimal("5"),
        Decimal("1"),
        Decimal("100"),
        "USD",
        date(2020, 1, 3),
    )
    baseline = get_account_gross_realised_pnl(factory, account.id)
    with factory() as uow:
        for type_ in [TransactionType.FEE, TransactionType.TAX]:
            for related in [buy.id, sell.id, None]:
                uow.transactions.add(
                    CanonicalTransaction(
                        account_id=account.id,
                        type=type_,
                        cash_amount=Decimal("1000"),
                        currency_code="RUB",
                        effective_date=date(2020, 1, 3),
                        related_transaction_id=related,
                    )
                )
        uow.commit()
    assert get_account_gross_realised_pnl(factory, account.id) == baseline
    earlier = create_buy(
        factory,
        account.id,
        instrument.id,
        Decimal("5"),
        Decimal("1"),
        Decimal("25"),
        "USD",
        date(2020, 1, 1),
    )
    assert earlier.id > sell.id
    updated = get_account_gross_realised_pnl(factory, account.id).sells[0]
    assert updated.matches[0].source_buy_transaction_id == earlier.id
    assert updated.matches[0].realised_pnl == ExactMoney(Fraction(75), "USD")
    with clean_db.begin() as session:
        session.execute(
            update(TransactionModel)
            .where(TransactionModel.id == sell.id)
            .values(effective_date=date(2019, 12, 31))
        )
    updated = get_account_gross_realised_pnl(factory, account.id).sells[0]
    assert updated.matches == () and updated.unmatched_proceeds is not None
    assert updated.effective_date == date(2019, 12, 31)
    assert updated.unmatched_proceeds.allocated_proceeds == ExactMoney(Fraction(100), "USD")
