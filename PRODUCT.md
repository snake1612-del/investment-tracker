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

## Long-term product intent

The original broad MVP described the following product outcomes. They remain the long-term intent, but are no longer all blockers for the first usable release:

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

## MVP v0.1 — Usable personal manual investment journal

Decision 016 re-baselines the first usable MVP. The existing F001–F005 financial foundation is retained; productisation takes priority over another calculation layer. This is the approved target, not a claim that the browser product is already implemented. See README for current capabilities.

### MUST HAVE

- Browse and create Portfolios, InvestmentAccounts and Instruments.
- Enter DEPOSIT / BUY / SELL through the web.
- Review Account transaction history and correct supported manual journal events before regular use.
- View Account / Portfolio positions and gross trade-cash realised P&L.
- Present unresolved/incomplete results honestly, preserve currency partitions, and distinguish gross realised P&L from net profit or total investment performance.
- Preserve data across reload/restart.
- Have an operational backup/restore workflow before regular real-data use.
- Establish an appropriate access-control boundary before untrusted/public deployment.

### SOON AFTER

- Remaining cash/income/expense events: WITHDRAWAL, DIVIDEND, COUPON, FEE and TAX.
- Valuation and unrealised result.
- One approved performance methodology and one benchmark.
- CSV import earlier only if real manual usage proves data entry is a blocker.

Performance and benchmark comparison remain core future product capabilities. They are not blockers for the first usable v0.1; Decision 016 updates the immediate-release interpretation of Decision 002 without abandoning its long-term value.

### LATER

- Broker integrations and automatic synchronization.
- Advanced FX methodology.
- Corporate actions.
- A tax engine.
- Advanced analytics.

## Current product capability — Manual Portfolio Workspace

“Investment Tracker can now let its owner record trades and inspect holdings and realised results in the browser.”

The browser now exposes the supported journal workflow, with minimal Portfolio/Account list reads for discovery. It introduces no new financial engine. Corrections remain required for MVP v0.1, but are not part of this first Workspace milestone. Backup/restore and an appropriate access boundary are also still required before regular real-data use.

## Long-term asset coverage

The product is intended to cover:

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

Already approved and no longer open:

- Web-first delivery, initial stack, module boundaries and persistence model: Decisions 004–009.
- Manual trade contracts and position/FIFO/realised-P&L capabilities: Decisions 010–015 and F001–F005.
- Immediate MVP scope and productisation priority: Decision 016.
- Exact-money presentation is approved for Manual Portfolio Workspace: native BigInt rationals, currency suffix, at most eight displayed decimal places, approximate values marked `≈`, no feedback into financial state or writes. The lossless API contract is unchanged.

The following remain open before their corresponding capabilities are implemented:

- Public correction workflow/contracts for supported manual events.
- Cash/income/expense calculations beyond the currently approved semantics.
- Valuation and unrealised-P&L methodology.
- Selection of the first performance measure and its methodology, including any TWR/XIRR work.
- Benchmark methodology.
- Market-data and FX providers and associated methodology.

Approved financial and engineering rules live in [CALCULATIONS.md](docs/CALCULATIONS.md) and [DECISIONS.md](docs/DECISIONS.md). Process v2 thresholds and Development autonomy are defined in [AGENTS.md](AGENTS.md); ordinary implementation details do not require separate decisions.
