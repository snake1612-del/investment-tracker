# Investment Tracker

> Personal investment analytics platform for portfolio tracking, performance analysis and benchmark comparison.

## Status

Investment Tracker has an initial persistence vertical slice. Portfolio analytics and further financial methodologies are still being designed.

## Goals

- Reconstruct a portfolio from transactions.
- Calculate real investment performance.
- Explain the sources of returns.
- Analyze income, fees, and taxes.
- Compare actual portfolio performance with alternative strategies.

## Current Stage

- A minimal Next.js web application and FastAPI service are available.
- The API can create a Portfolio, InvestmentAccount, and DEPOSIT transaction, then read account transactions.
- Portfolio calculations, other transaction types, and frontend product features have not been implemented.

## Documentation

- [Product definition](PRODUCT.md)
- [Decision log](docs/DECISIONS.md)

## Development

The project requires Node.js 24, pnpm, Python 3.14, and uv. Architectural and financial decisions must be explicitly documented before they are implemented.

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

From the repository root, start the local PostgreSQL service:

```bash
docker compose up -d db
```

From `apps/api`, install dependencies and copy `.env.example` to a local `.env` file. The example contains disposable local credentials only. Then apply the schema and start the API:

```bash
uv sync
uv run --env-file .env alembic upgrade head
uv run --env-file .env uvicorn app.main:app --reload
```

Unit tests run without PostgreSQL. The full suite and migration drift check require the local database:

```bash
uv run pytest tests/unit
uv run --env-file .env pytest
uv run --env-file .env alembic check
uv run ruff check .
uv run ruff format --check .
uv run pyright app tests
```

From the repository root, stop the database with `docker compose stop db` or remove the container and network while preserving data with `docker compose down`.

To deliberately erase all local database data, run `docker compose down -v`, restart with `docker compose up -d db`, then apply migrations again from `apps/api` with `uv run --env-file .env alembic upgrade head`.
