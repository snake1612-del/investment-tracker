# Product Definition

## Product Vision

Investment Tracker is a personal platform for tracking and analyzing an investment portfolio.

It should answer:

- What is currently held in the portfolio?
- How much money has been contributed?
- How much has the user actually earned or lost?
- What were the sources of the result?
- How much came from dividends and coupons?
- How much was lost to fees and taxes?
- Which assets contributed most to the result?
- How does the result compare with an alternative strategy?

## Product Positioning

Investment Tracker is not:

- A broker.
- A trading terminal.
- An investment signal service.
- A financial adviser.
- A social network.

It is an analytics layer over investment accounts and transaction history.

## Target User

The first version is intended for:

- One user.
- A private investor.
- One or more brokerage or investment accounts.
- Purchases and sales.
- Deposits and withdrawals.
- Dividends and coupons.
- Fees and taxes.

## Product Principles

### Correctness over number of metrics

Correct financial calculations are more important than the number of available analytics metrics.

### Transactions are the basis of portfolio history

Portfolio history must be reconstructed from transactions.

### Financial logic must be explicit

Codex must not invent financial methodology. Rules and methodologies including the following must be designed and documented separately before implementation:

- Cost basis.
- FIFO.
- Realised P&L.
- Unrealised P&L.
- Time-weighted return (TWR).
- Extended internal rate of return (XIRR).
- Benchmark calculations.
- Foreign-exchange effect.

### Tests for financial calculations

Critical financial calculations must have automated tests and reference scenarios with known expected results.

## MVP

The MVP should allow the user to:

1. Create a portfolio.
2. Create an investment account.
3. Enter transactions.
4. Reconstruct positions.
5. View portfolio value.
6. View invested capital.
7. View profit and loss.
8. View dividends and coupons.
9. View fees and taxes.
10. Review transaction history.
11. View performance history.
12. Compare the portfolio with an initial benchmark.

## MVP Transaction Types

The first version is expected to support:

- Deposit.
- Withdrawal.
- Buy.
- Sell.
- Dividend.
- Coupon.
- Fee.
- Tax.

## Assets

The first version is intended to cover:

- Stocks.
- Bonds.
- Funds.
- Cash.

## Not in MVP

The following are not part of the MVP:

- Broker APIs.
- Automatic synchronization.
- An advanced tax engine.
- Predictions.
- Portfolio recommendations.
- Complex risk analytics.
- Social features.
- A native mobile application.

## Open Decisions

The following decisions have not yet been made:

- Web, PWA, or desktop delivery.
- Final technology stack.
- Architecture.
- Data model.
- Cost basis methodology.
- Realised and unrealised P&L methodology.
- TWR methodology.
- XIRR methodology.
- Benchmark methodology.
- Market data provider.
- FX data provider.
