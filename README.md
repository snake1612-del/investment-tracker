# Investment Tracker

> Personal investment analytics platform for portfolio tracking, performance analysis and benchmark comparison.

## Status

Investment Tracker is a single-user investment tracker with a working financial backend/API. The web application is still a scaffold, not a usable investment journal.

The revised MVP v0.1 is a usable personal manual investment journal. Productisation now takes priority over another calculation layer; the next product milestone is **Manual Portfolio Workspace**. See [PRODUCT.md](PRODUCT.md) and [Decision 016](docs/DECISIONS.md#decision-016--mvp-v01-re-baseline) for the approved scope.

## Goals

- Reconstruct a portfolio from transactions.
- Calculate real investment performance.
- Explain the sources of returns.
- Analyze income, fees, and taxes.
- Compare actual portfolio performance with alternative strategies.

## Current Stage

- The API persists Portfolio, InvestmentAccount and Instrument records, accepts manual DEPOSIT / BUY / SELL, and reads Account transaction history.
- Public Account and Portfolio reads expose exact position quantities and gross trade-cash realised P&L.
- FIFO lots and cost-basis reconstruction are internal, recomputable derived capabilities, not public lot/cost-basis APIs.
- Financial facts preserve independent quantity / price / cash inputs. Realised P&L uses exact rational money, remains partitioned by currency, and explicitly reports unresolved missing-basis or currency-mismatch components. It is not net, tax-adjusted or FX-converted profit.
- These capabilities are usable through API clients only. Browser workflows, Portfolio/Account browsing and journal corrections are not implemented. Valuation, unrealised P&L, performance, benchmark and imports remain future capabilities.

## Documentation

- [Product definition](PRODUCT.md)
- [Decision log](docs/DECISIONS.md)
- [Financial methodology](docs/CALCULATIONS.md)
- [Repository workflow](AGENTS.md)

## Development

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
```

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
