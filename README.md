# Investment Tracker

> Personal investment analytics platform for portfolio tracking, performance analysis and benchmark comparison.

## Status

Investment Tracker is a single-user investment tracker with a working financial backend/API and a Manual Portfolio Workspace in the browser.

The revised MVP v0.1 is a usable personal manual investment journal. Manual Portfolio Workspace and Journal Corrections provide browser entry and correction workflows; backup/restore and an appropriate access boundary remain prerequisites for regular real-data use. See [PRODUCT.md](PRODUCT.md) and [Decision 016](docs/DECISIONS.md#decision-016--mvp-v01-re-baseline) for the approved scope.

## Goals

- Reconstruct a portfolio from transactions.
- Calculate real investment performance.
- Explain the sources of returns.
- Analyze income, fees, and taxes.
- Compare actual portfolio performance with alternative strategies.

## Current Stage

- The API persists Portfolio, InvestmentAccount and Instrument records, accepts all eight manual canonical transaction types, and reads Account transaction history.
- Public Account and Portfolio reads expose exact position quantities, gross trade-cash realised P&L, and as-of-date Money summaries with recorded cash and separate income/outflow totals by currency.
- FIFO lots and cost-basis reconstruction are internal, recomputable derived capabilities, not public lot/cost-basis APIs.
- Financial facts preserve independent quantity / price / cash inputs. Realised P&L uses exact rational money, remains partitioned by currency, and explicitly reports unresolved missing-basis or currency-mismatch components. It is not net, tax-adjusted or FX-converted profit.
- The browser supports Portfolio/Account browsing and creation, Instrument selection/creation, manual DEPOSIT / WITHDRAWAL / BUY / SELL / DIVIDEND / COUPON / FEE / TAX, Account History with edit/hard-delete for all eight types, and Account/Portfolio Holdings, Money and gross realised results. Fee/Tax can be standalone or linked for context. Valuation, unrealised P&L, performance, benchmark and imports remain future capabilities.

## Documentation

- [Product definition](PRODUCT.md)
- [Decision log](docs/DECISIONS.md)
- [Financial methodology](docs/CALCULATIONS.md)
- [Local runtime and operations](docs/OPERATIONS.md)
- [Repository workflow](AGENTS.md)

## Development

### Local Docker (recommended)

With Docker Desktop running, from the repository root:

```bash
docker compose up --build
```

Open `http://localhost:3000`; the API is at `http://localhost:8000` and PostgreSQL at `127.0.0.1:55432`. API startup applies Alembic migrations before serving; both source trees hot-reload. Stop with `docker compose down` to preserve database data. See [OPERATIONS](docs/OPERATIONS.md) for logs, rebuilds, persistence and isolated testing.

Cloud runtime remains pending provisioning, blocked by Supabase project quota. The following host-run workflows remain available; tests/E2E must use the disposable test database, never the normal Docker API/database.

The project requires Node.js 24, pnpm, Python 3.14, and uv. New financial semantics and durable architectural changes require approved decisions; ordinary implementation details follow the existing rules in [AGENTS.md](AGENTS.md).

### Web

From `apps/web`:

```bash
pnpm install
pnpm dev
```

Checks:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm format:check
pnpm build
```

Start the API on `127.0.0.1:8000` and open the web server (normally `http://localhost:3000`). Web requests use a same-origin `/api` rewrite to the API; set the server-side `API_URL` before starting/building web if the API endpoint differs. This is a local single-user workflow, not an authentication or public-deployment boundary.

Workspace context is Portfolio → Account, with a Portfolio summary option. Account views are Holdings / History / Money / Realised result; Portfolio summary has Holdings / Money / Realised result, without transaction entry or History. Creation and recording use dialogs. BUY/SELL quantity, price and cash remain independent decimal-string inputs; mismatch and oversell do not block valid entry. Income entry requires gross income; known withholding is a separate Tax, and net-only source data is deferred.

History Edit replaces approved factual fields in place, preserving ID, type, Account, creation metadata and note. Fee/Tax optional Instrument and relation are editable with explicit clearing. Delete requires confirmation and permanently removes the canonical event; there is no undo or audit history. Both refresh History, Holdings, Money and Realised result. Derived matches never block a correction, but an inbound canonical related transaction blocks deletion (409), until its Fee/Tax link is explicitly cleared/changed or its child deleted. Backdated corrections can change FIFO and past realised results; concurrent stale-tab writes are last-write-wins. See F006–F008 and Decisions 017–018 for the complete contract.

Money uses an explicit as-of effective date, initially browser-local today. Changing that date refetches Money only, and changing Account/Portfolio resets it. Recorded cash can be negative and is not available/settled broker cash. All amounts remain exact scale-eight decimal strings, including totals beyond canonical input width; no approximate display, FX total, net income or net P&L is introduced. Fee/Tax do not affect gross trade-cash realised P&L.

Exact-money presentation uses native BigInt rationals, currency suffixes and at most eight decimal places. Non-exact display rounding is half away from zero and marked `≈`; original rational values remain unchanged and display values never feed writes/calculations. No currency totals or FX conversion are performed.

### Browser E2E

The Playwright suite covers the full journal journey, incomplete oversell results, correction/deletion of a consumed BUY, and gross income/linked Tax/Money/correction/FK-conflict flows on desktop and narrow viewports. It writes uniquely named synthetic records through the browser, so **do not point its API at a personal/development-data database**.

First run the full backend tests below to initialize/recreate the disposable `investment_tracker_test` database. After those tests finish, start a separate API process with `DATABASE_URL` set to:

```text
postgresql+psycopg://investment_tracker:local_development_only@127.0.0.1:55432/investment_tracker_test
```

Then, from `apps/web`:

```bash
pnpm exec playwright install chromium
pnpm test:e2e
```

Do not run backend tests concurrently with E2E: backend tests recreate that database. Playwright starts web when needed and expects the API already running on port 8000. `WEB_PORT` overrides the default web port 3000 if occupied; `API_URL` overrides the rewrite target. Stop the test API/web processes afterwards; the next backend test run recreates disposable records. Existing GitHub CI checks are unchanged; E2E is currently a separate local verification command.

### API

The repository-owned PostgreSQL service is published only at `127.0.0.1:55432`; its container port remains `5432`. It does not use or modify a separately installed Windows PostgreSQL on host port `5432`. No external Compose override is needed.

From the repository root, validate and start the service, then confirm the endpoint:

```bash
docker compose config --quiet
docker compose up -d --wait db
docker compose port db 5432
```

The last command must report `127.0.0.1:55432`.

From `apps/api`, install dependencies and copy `.env.example` to an ignored local `.env` file. The example contains disposable local credentials only. If `.env` already exists, update its database host/port to `127.0.0.1:55432`; do not keep the old `localhost:5432` URLs.

Local URL convention:

```text
DATABASE_URL=postgresql+psycopg://investment_tracker:local_development_only@127.0.0.1:55432/investment_tracker
TEST_DATABASE_URL=postgresql+psycopg://investment_tracker:local_development_only@127.0.0.1:55432/investment_tracker_test
```

Then apply the schema and start the API:

```bash
uv sync --locked
uv run --env-file .env alembic upgrade head
uv run --env-file .env uvicorn app.main:app --reload
```

For canonical local PostgreSQL verification, use the committed disposable configuration directly from `apps/api`, so a stale local `.env` is not selected:

```bash
uv run --env-file .env.example alembic upgrade head
uv run --env-file .env.example pytest
uv run --env-file .env.example alembic check
```

Before running, ensure the shell does not already export `DATABASE_URL` or `TEST_DATABASE_URL`: exported values take precedence over the env file. Confirm the Compose endpoint above rather than substituting port `5432`.

Tests recreate only `investment_tracker_test` on that local server; do not use this database for personal records. Existing test URL guards reject query overrides, non-local hosts, unexpected database names and mismatched development/test server coordinates.

GitHub CI continues to use its own isolated PostgreSQL service on `localhost:5432` with CI credentials. The `Web`, `API quality` and `API PostgreSQL` checks are unchanged.

Other checks:

```bash
uv run pytest tests/unit
uv run ruff check .
uv run ruff format --check .
uv run pyright app tests
```

From the repository root, stop the database with `docker compose stop db` or remove the container and network while preserving data with `docker compose down`.

`docker compose down -v` deliberately erases the repository's local database volume; it is not part of the normal test/stop workflow. Operational backup/restore is required before regular real-data use. The local disposable configuration is not a production deployment or an access-control solution.
