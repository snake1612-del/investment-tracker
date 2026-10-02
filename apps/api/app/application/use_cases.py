"""Typed use-case functions for the first persistence vertical slice."""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from app.application.contracts import (
    AccountRecord,
    InstrumentRecord,
    PortfolioRecord,
    PositionRecord,
    RealisedPnlReadRecord,
    TransactionRecord,
    UnitOfWork,
    UnresolvedPnlRecord,
)
from app.domain.instruments import normalized_instrument_name
from app.domain.portfolio.engine.fifo import (
    AccountCostBasisSummary,
    ExactMoney,
    FifoReconstruction,
    LotTransactionFact,
    PortfolioCostBasisSummary,
    aggregate_portfolio_summaries,
    reconstruct_fifo_lots,
    summarize_account,
)
from app.domain.portfolio.engine.positions import reconstruct_positions
from app.domain.portfolio.engine.realised_pnl import (
    AccountGrossRealisedPnlSummary,
    GrossRealisedPnlReconstruction,
    PortfolioGrossRealisedPnlSummary,
    aggregate_portfolio_gross_realised_pnl,
    reconstruct_gross_realised_pnl,
    summarize_account_gross_realised_pnl,
)
from app.domain.transactions import CanonicalTransaction, TransactionType, valid_currency_code


class NotFound(Exception):
    """A requested canonical entity does not exist."""


class InvalidInput(ValueError):
    """An application input is invalid."""


class PersistenceConflict(Exception):
    """A known persistence constraint was violated."""


class PositionDataIntegrityError(RuntimeError):
    """A reconstructed position cannot be enriched from canonical metadata."""


class RealisedPnlDataIntegrityError(RuntimeError):
    """A reconstructed P&L component lacks canonical source metadata."""


UowFactory = Callable[[], UnitOfWork]


def list_portfolios(factory: UowFactory) -> list[PortfolioRecord]:
    with factory() as uow:
        return uow.portfolios.list()


def list_portfolio_accounts(factory: UowFactory, portfolio_id: int) -> list[AccountRecord]:
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        return uow.accounts.list_for_portfolio(portfolio_id)


def create_portfolio(factory: UowFactory, name: str, base_currency: str) -> PortfolioRecord:
    if not name.strip() or not valid_currency_code(base_currency):
        raise InvalidInput("Portfolio name and three-letter uppercase base currency are required")
    with factory() as uow:
        result = uow.portfolios.add(name, base_currency)
        uow.commit()
        return result


def create_investment_account(factory: UowFactory, portfolio_id: int, name: str) -> AccountRecord:
    if not name.strip():
        raise InvalidInput("Investment account name is required")
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        result = uow.accounts.add(portfolio_id, name)
        uow.commit()
        return result


def create_instrument(factory: UowFactory, name: str) -> InstrumentRecord:
    trimmed_name = normalized_instrument_name(name)
    with factory() as uow:
        result = uow.instruments.add(trimmed_name)
        uow.commit()
        return result


def list_instruments(factory: UowFactory) -> list[InstrumentRecord]:
    with factory() as uow:
        return uow.instruments.list()


def create_deposit(
    factory: UowFactory,
    account_id: int,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    note: str | None = None,
) -> TransactionRecord:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        transaction = CanonicalTransaction.deposit(
            account_id, cash_amount, currency_code, effective_date, note
        )
        result = uow.transactions.add(transaction)
        uow.commit()
        return result


def create_buy(
    factory: UowFactory,
    account_id: int,
    instrument_id: int,
    quantity: Decimal,
    price: Decimal,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    settlement_date: date | None = None,
    note: str | None = None,
) -> TransactionRecord:
    return _create_manual_trade(
        factory,
        TransactionType.BUY,
        account_id,
        instrument_id,
        quantity,
        price,
        cash_amount,
        currency_code,
        effective_date,
        settlement_date,
        note,
    )


def create_sell(
    factory: UowFactory,
    account_id: int,
    instrument_id: int,
    quantity: Decimal,
    price: Decimal,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    settlement_date: date | None = None,
    note: str | None = None,
) -> TransactionRecord:
    return _create_manual_trade(
        factory,
        TransactionType.SELL,
        account_id,
        instrument_id,
        quantity,
        price,
        cash_amount,
        currency_code,
        effective_date,
        settlement_date,
        note,
    )


def _create_manual_trade(
    factory: UowFactory,
    trade_type: TransactionType,
    account_id: int,
    instrument_id: int,
    quantity: Decimal,
    price: Decimal,
    cash_amount: Decimal,
    currency_code: str,
    effective_date: date,
    settlement_date: date | None,
    note: str | None,
) -> TransactionRecord:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        if uow.instruments.get(instrument_id) is None:
            raise NotFound("Instrument not found")
        constructor = (
            CanonicalTransaction.buy
            if trade_type is TransactionType.BUY
            else CanonicalTransaction.sell
        )
        transaction = constructor(
            account_id,
            instrument_id,
            quantity,
            price,
            cash_amount,
            currency_code,
            effective_date,
            settlement_date,
            note,
        )
        result = uow.transactions.add(transaction)
        uow.commit()
        return result


def list_account_transactions(factory: UowFactory, account_id: int) -> list[TransactionRecord]:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        return uow.transactions.list_for_account(account_id)


def _canonical_from_record(record: TransactionRecord) -> CanonicalTransaction:
    """Map factual persisted history to the existing domain representation."""
    return CanonicalTransaction(
        account_id=record.account_id,
        type=record.type,
        cash_amount=record.cash_amount,
        currency_code=record.currency_code,
        effective_date=record.effective_date,
        instrument_id=record.instrument_id,
        related_transaction_id=record.related_transaction_id,
        quantity=record.quantity,
        price=record.price,
        settlement_date=record.settlement_date,
        note=record.note,
    )


def _lot_fact_from_record(record: TransactionRecord) -> LotTransactionFact:
    """Explicit F004 boundary: only persisted identity and required canonical facts."""
    return LotTransactionFact(
        transaction_id=record.id,
        account_id=record.account_id,
        type=record.type,
        instrument_id=record.instrument_id,
        quantity=record.quantity,
        cash_amount=record.cash_amount,
        currency_code=record.currency_code,
        effective_date=record.effective_date,
    )


def _account_fifo(uow: UnitOfWork, account_id: int) -> FifoReconstruction:
    return _load_account_fifo_context(uow, account_id)[1]


def _load_account_fifo_context(
    uow: UnitOfWork, account_id: int
) -> tuple[tuple[LotTransactionFact, ...], FifoReconstruction]:
    facts = tuple(map(_lot_fact_from_record, uow.transactions.list_for_account(account_id)))
    return facts, reconstruct_fifo_lots(facts, account_id=account_id)


def _account_gross_realised_pnl(uow: UnitOfWork, account_id: int) -> GrossRealisedPnlReconstruction:
    facts, fifo = _load_account_fifo_context(uow, account_id)
    return reconstruct_gross_realised_pnl(fifo, facts)


def get_account_gross_realised_pnl(
    factory: UowFactory, account_id: int
) -> GrossRealisedPnlReconstruction:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        return _account_gross_realised_pnl(uow, account_id)


def get_account_gross_realised_pnl_summary(
    factory: UowFactory, account_id: int
) -> AccountGrossRealisedPnlSummary:
    return summarize_account_gross_realised_pnl(get_account_gross_realised_pnl(factory, account_id))


def get_portfolio_gross_realised_pnl_summary(
    factory: UowFactory, portfolio_id: int
) -> PortfolioGrossRealisedPnlSummary:
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        return aggregate_portfolio_gross_realised_pnl(
            summarize_account_gross_realised_pnl(_account_gross_realised_pnl(uow, account.id))
            for account in uow.accounts.list_for_portfolio(portfolio_id)
        )


def get_account_fifo(factory: UowFactory, account_id: int) -> FifoReconstruction:
    """Internal read capability; no public rational-money contract or commit."""
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        return _account_fifo(uow, account_id)


def get_account_realised_pnl_read(factory: UowFactory, account_id: int) -> RealisedPnlReadRecord:
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        reconstruction = _account_gross_realised_pnl(uow, account_id)
        summary = summarize_account_gross_realised_pnl(reconstruction)
        return _realised_pnl_read_record(uow, (reconstruction,), summary.resolved_pnl_by_currency)


def get_portfolio_realised_pnl_read(
    factory: UowFactory, portfolio_id: int
) -> RealisedPnlReadRecord:
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        reconstructions = tuple(
            _account_gross_realised_pnl(uow, account.id)
            for account in uow.accounts.list_for_portfolio(portfolio_id)
        )
        summary = aggregate_portfolio_gross_realised_pnl(
            summarize_account_gross_realised_pnl(reconstruction)
            for reconstruction in reconstructions
        )
        return _realised_pnl_read_record(uow, reconstructions, summary.resolved_pnl_by_currency)


def _realised_pnl_read_record(
    uow: UnitOfWork,
    reconstructions: Sequence[GrossRealisedPnlReconstruction],
    resolved: Mapping[str, ExactMoney],
) -> RealisedPnlReadRecord:
    """Enrich the already computed result; no history reload or reconstruction."""
    names = {instrument.id: instrument.name for instrument in uow.instruments.list()}
    unresolved: list[UnresolvedPnlRecord] = []
    for reconstruction in reconstructions:
        if reconstruction.account_id is None:
            raise RealisedPnlDataIntegrityError("Missing reconstruction Account identity")
        for sell in reconstruction.sells:
            for component in sell.unresolved_components:
                if component.instrument_id not in names:
                    raise RealisedPnlDataIntegrityError(
                        "Realised P&L Instrument metadata is missing"
                    )
                unresolved.append(
                    UnresolvedPnlRecord(
                        reconstruction.account_id,
                        names[component.instrument_id],
                        sell.effective_date,
                        component,
                    )
                )
    # Stable sorting preserves match order, followed by unmatched proceeds, within a SELL.
    unresolved.sort(
        key=lambda item: (item.effective_date, item.component.source_sell_transaction_id)
    )
    return RealisedPnlReadRecord(
        tuple(resolved[currency] for currency in sorted(resolved)), tuple(unresolved)
    )


def get_account_cost_basis(
    factory: UowFactory, account_id: int
) -> tuple[AccountCostBasisSummary, ...]:
    return summarize_account(get_account_fifo(factory, account_id))


def get_portfolio_cost_basis(
    factory: UowFactory, portfolio_id: int
) -> tuple[PortfolioCostBasisSummary, ...]:
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        accounts = uow.accounts.list_for_portfolio(portfolio_id)
        return aggregate_portfolio_summaries(
            summarize_account(_account_fifo(uow, account.id)) for account in accounts
        )


def get_account_positions(factory: UowFactory, account_id: int) -> list[PositionRecord]:
    """Read current UTC-date quantities without mutating canonical history."""
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        history = uow.transactions.list_for_account(account_id)
        as_of_date = datetime.now(UTC).date()
        quantities = reconstruct_positions(map(_canonical_from_record, history), as_of_date)
        return _position_records(uow, quantities)


def get_portfolio_positions(factory: UowFactory, portfolio_id: int) -> list[PositionRecord]:
    """Reconstruct one Portfolio from only its Accounts' canonical histories."""
    with factory() as uow:
        if uow.portfolios.get(portfolio_id) is None:
            raise NotFound("Portfolio not found")
        accounts = uow.accounts.list_for_portfolio(portfolio_id)
        as_of_date = datetime.now(UTC).date()
        history = [
            _canonical_from_record(record)
            for account in accounts
            for record in uow.transactions.list_for_account(account.id)
        ]
        quantities = reconstruct_positions(history, as_of_date)
        return _position_records(uow, quantities)


def _position_records(uow: UnitOfWork, quantities: dict[int, Decimal]) -> list[PositionRecord]:
    nonzero = {
        instrument_id: quantity for instrument_id, quantity in quantities.items() if quantity
    }
    names = {instrument.id: instrument.name for instrument in uow.instruments.list()}
    positions: list[PositionRecord] = []
    for instrument_id in sorted(nonzero):
        if instrument_id not in names:
            raise PositionDataIntegrityError("Position Instrument metadata is missing")
        positions.append(
            PositionRecord(instrument_id, names[instrument_id], nonzero[instrument_id])
        )
    return positions
