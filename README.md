# Investment Tracker

> Personal investment analytics platform for portfolio tracking, performance analysis and benchmark comparison.

## Status

Investment Tracker is at the initial application scaffold stage. Product scope and financial methodologies are still being designed.

## Goals

- Reconstruct a portfolio from transactions.
- Calculate real investment performance.
- Explain the sources of returns.
- Analyze income, fees, and taxes.
- Compare actual portfolio performance with alternative strategies.

## Current Stage

- A minimal Next.js web application and FastAPI service are available.
- The API currently exposes only a liveness endpoint.
- Portfolio, transaction, persistence, and financial calculation features have not been implemented.

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

From `apps/api`:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright app tests
uv run pytest
```
