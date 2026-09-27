# Decision Log

This document records significant product and technical decisions. New decisions should be added as they are approved; prior decisions should remain visible or be explicitly superseded.

## Decision 001 — Single-user first version

**Decision**

The first version of the product is intended for one user.

**Reason**

This allows the initial work to focus on the transaction model, financial calculations, and analytics without introducing authentication and user-management complexity.

**Consequence**

The architecture should not intentionally prevent future multi-user support, but multi-user functionality is not a requirement for the first MVP.

---

## Decision 002 — Performance comparison is a core product capability

**Decision**

Performance and benchmark comparison must be introduced early and are part of the product's core value.

**Reason**

The product must answer not only "What is the portfolio worth?" but also help explain the quality of the investment result relative to an alternative.

**Consequence**

Transaction and cash-flow history must be stored in a way that supports correct future performance calculations and benchmark scenarios.

---

## Decision 003 — Repository documentation is the source of truth

**Decision**

Approved product and technical decisions must be recorded progressively in the repository documentation.

**Reason**

Work takes place across multiple ChatGPT and Codex chats, so chat history must not be the only place where important decisions are stored.

**Consequence**

Relevant project documents must be updated whenever a significant decision changes.

---

## Decision 004 — Web-first application

**Decision**

The first version of Investment Tracker will be developed as a responsive web application.

The architecture should allow PWA capabilities to be added gradually.

A desktop or native mobile client is not a requirement for the first version.

**Reason**

The web provides the simplest path for development and testing, is well suited to analytical interfaces, tables, and charts, works across multiple operating systems, and does not require a separate desktop or mobile distribution pipeline.

User file imports can be implemented using standard browser capabilities and do not require a desktop application.

**Consequence**

The frontend will be designed as a responsive web UI.

The backend and financial calculation core must not depend on a specific client platform.

In the future, the web frontend may be extended into a PWA, used inside a desktop wrapper, or supplemented with a separate mobile client.

---

## Decision 005 — Initial technology stack

**Decision**

Investment Tracker will use separate frontend and backend applications within a single repository.

Initial stack:

Frontend:

- Next.js.
- React.
- TypeScript.

Backend:

- Python.
- FastAPI.

Database:

- PostgreSQL.

ORM:

- SQLAlchemy.

Migrations:

- Alembic.

Backend testing:

- pytest.

Frontend testing:

- Vitest.
- React Testing Library.

End-to-end testing:

- Playwright.

The backend will evolve as a modular monolith.

Microservices will not be used at this stage.

The Financial / Portfolio Engine must be a framework-independent Python domain layer and must not directly depend on:

- React.
- Next.js.
- FastAPI handlers.
- SQLAlchemy.
- Specific broker APIs.
- Specific CSV, XLSX, or broker-report formats.

**Reason**

Full-stack Next.js is a viable option and would be simpler at the initial stage.

A separate Python backend was selected not because individual financial formulas such as FIFO, realised P&L, TWR, or XIRR inherently require Python.

The primary reason is the planned combination of backend responsibilities:

- Portfolio reconstruction.
- Financial calculations.
- Historical analytics.
- CSV, XLSX, and broker-report ingestion.
- Market-data processing.
- Benchmark simulation.
- Repeated portfolio recalculation.
- Future scheduled broker and market-data integrations.

For this combination, Python provides a suitable data-processing ecosystem, while a separate backend boundary prevents the financial core from becoming coupled to the web client.

**Consequences**

The project will use two runtimes and two dependency ecosystems:

- TypeScript / Node.js.
- Python.

This increases the initial complexity compared with full-stack Next.js.

Financial calculations must not reside in React components or FastAPI route handlers.

The HTTP/API layer must not contain database queries directly. Data access must be separated from transport and application logic.

Monetary values and accounting quantities that require precise decimal arithmetic must use an exact decimal representation rather than binary floating point.

External broker, market-data, and file formats must be normalized into internal models before being passed to the Portfolio Engine.

Database schema changes must be managed through Alembic migrations.

A financial feature is considered complete only after:

1. Its methodology has been defined.
2. It has been implemented.
3. It has automated tests.

---

## Decision 006 — Repository and backend module structure

**Decision**

Investment Tracker remains a single repository with separate web and API applications:

```text
investment-tracker/
├── apps/
│   ├── web/
│   └── api/
├── docs/
├── README.md
├── PRODUCT.md
└── .gitignore
```

The backend is organized as a modular monolith with four primary logical layers:

```text
apps/api/app/
├── api/
├── application/
├── domain/
├── infrastructure/
├── bootstrap.py
└── main.py
```

These directories define architectural boundaries.

They do not mean that all nested directories and empty files must be created in advance. Specific modules are added only with real functionality.

### domain

Contains framework-independent financial business logic:

- Domain models.
- Value objects.
- Enums.
- Financial rules.
- Portfolio Engine.
- Pure calculations.
- Domain services.

The Portfolio Engine will logically reside within:

```text
domain/portfolio/engine/
```

and may eventually include:

- Cost basis.
- Positions.
- Realised / unrealised P&L.
- Cash flows.
- Performance.
- Benchmarks.
- FX.

Specific financial modules are created only after the corresponding methodology has been approved.

The domain must not depend on:

- FastAPI.
- Pydantic.
- SQLAlchemy.
- PostgreSQL drivers.
- Infrastructure.
- Application.
- Broker SDKs.
- File parsers.
- Frontend concepts.

Initially, domain models should use ordinary Python types, dataclasses, Decimal, date/datetime, and Enum.

### application

Contains:

- Use cases.
- Orchestration.
- Application services.
- Command/query inputs.
- Result objects.
- Minimal contracts for external dependencies when they are genuinely needed.

The application layer may depend on the domain.

The application layer must not depend on:

- FastAPI.
- SQLAlchemy.
- Concrete infrastructure implementations.

The application layer is retained from v1 so that orchestration does not move into FastAPI routes and can later also be used by background jobs, import processes, or a CLI.

### api

Contains the FastAPI-specific boundary:

- Routes.
- Request/response schemas.
- HTTP validation.
- Status codes.
- FastAPI dependencies.
- Mapping between HTTP models and application inputs/results.

API routes must remain thin.

Routes must not contain:

- Financial calculations.
- Portfolio reconstruction.
- SQLAlchemy queries.
- Broker parsing.
- Complex orchestration.

### infrastructure

Contains concrete interaction with external systems.

At the initial stage, this is primarily persistence:

```text
infrastructure/db/
```

Later, and only when real functionality appears, the following may be added:

- Brokers.
- Market data.
- Imports.

Infrastructure may contain:

- SQLAlchemy models.
- Engine/session factory.
- Persistence implementations.
- SQL queries.
- PostgreSQL-specific behavior.
- Broker clients.
- Market-data clients.
- CSV/XLSX parsers.
- External API adapters.

Infrastructure may depend on domain and application contracts.

Domain and application must not depend on concrete infrastructure implementations.

### Composition root

`bootstrap.py` is used as a simple composition root where concrete infrastructure is connected to application use cases and API dependencies.

A separate dependency injection framework is not used.

If a separate `bootstrap.py` is not yet needed in the initial scaffold because there is no wiring, a complex structure should not be created artificially. The composition root nevertheless remains a distinct architectural responsibility.

`main.py` is the FastAPI application entry point and must not contain financial business logic or a large amount of infrastructure wiring.

## Dependency direction

The primary direction is:

```text
API → Application → Domain
```

Infrastructure implements the necessary application contracts and may work with domain models.

The domain is the innermost layer.

The domain may import only:

- Python standard library.
- Other domain modules.

The application layer may import:

- Domain.
- Python standard library.
- Its own contracts/types.

The application layer does not import concrete infrastructure implementations.

The API calls application use cases.

Concrete infrastructure implementations are connected to the application and API at the composition-root level.

## Database and transaction boundaries

The SQLAlchemy Session is created and configured inside `infrastructure/db`.

The SQLAlchemy Session is not passed into the domain.

HTTP handlers do not perform database queries directly.

The application layer defines the logical transaction boundary of a use case.

Concrete begin / commit / rollback behavior is implemented through infrastructure.

A Unit of Work is not created in advance.

A minimal Unit of Work contract may be introduced only when a specific mutating use case genuinely requires atomic changes across multiple persistence operations.

## Repository Pattern

Repository abstractions are created only where they represent a useful domain/application capability.

The following rule is not used:

```text
one database table = one repository
```

The following are not created in advance:

- BaseRepository.
- GenericRepository.
- RepositoryFactory.
- RepositoryProvider.
- An interface hierarchy for every CRUD entity.

An abstraction must emerge from a use-case need, not from the existence of a table.

## Tests

Backend tests are located separately:

```text
apps/api/tests/
├── unit/
│   ├── domain/
│   └── application/
├── golden/
│   └── portfolio/
├── integration/
│   └── db/
└── api/
```

### unit/domain

Financial unit tests.

They do not require:

- PostgreSQL.
- FastAPI.
- Network access.
- A browser.

### unit/application

Tests use cases with simple fakes/stubs instead of infrastructure.

### golden/portfolio

Known input dataset → Portfolio Engine → known expected result.

These tests protect the financial methodology against regressions.

### integration/db

Tests:

- SQLAlchemy mappings.
- Persistence.
- Constraints.
- Transaction behavior.
- PostgreSQL integration.

### api

Tests the FastAPI HTTP boundary:

- Validation.
- Status codes.
- Serialization.
- API contracts.
- Application integration.

## Frontend

Decision 006 defines only:

```text
apps/web/
```

The internal frontend folder structure is not defined yet.

The following are not defined in advance:

- Features.
- Components.
- Hooks.
- Stores.
- Services.
- Lib.
- API.

This structure will be determined after the first real frontend features appear.

## Shared code

A top-level `packages/` directory is not created now.

The backend uses Python and the frontend uses TypeScript, so a shared runtime package does not currently provide value.

The API contract should eventually be built through:

```text
FastAPI / Pydantic API schemas
→ OpenAPI
→ generated TypeScript types/client
→ Next.js
```

rather than through manual duplication of Python and TypeScript models.

## What we deliberately do not create yet

The following are not created in advance:

- `packages/`.
- `workers/`.
- Top-level `shared/`.
- Top-level `common/`.
- Microservices.
- Redis.
- Celery.
- RabbitMQ.
- Kafka.
- Event bus.
- CQRS.
- Event sourcing.
- DI container.
- Generic repository framework.
- Broker adapter folders.
- Market-data adapter folders.
- Import infrastructure folders.
- A separate Portfolio Engine package.

**Reason**

Investment Tracker requires a clear separation between financial business logic, HTTP, and persistence, but it is developed by one person and does not need enterprise-level boilerplate.

Explicit `domain`, `application`, `api`, and `infrastructure` boundaries make it possible to:

- Test the Portfolio Engine independently.
- Keep orchestration out of FastAPI routes.
- Avoid coupling the domain to PostgreSQL.
- Add imports, brokers, market data, and background jobs later without moving financial logic.

The separate application layer is retained because orchestration must be usable not only from HTTP but also by future imports and background processes.

Infrastructure remains a single layer and is divided into additional submodules only as real integrations appear.

**Consequences**

The backend gains a small amount of additional structural complexity from the four explicit layers.

At the same time:

- The domain remains framework-independent.
- Financial tests run without external services.
- Routes remain thin.
- Persistence is separated from HTTP.
- Infrastructure depends inward, not the other way around.
- New abstractions are created only when there is a concrete need.

---

## Decision 007 — Initial project scaffold and developer tooling

**Decision**

The initial repository scaffold contains two independently managed applications:

- `apps/web` for the Next.js, React, and TypeScript frontend.
- `apps/api` for the Python and FastAPI backend.

The web application uses the Node.js 24 release line and pnpm. It uses the App Router, a `src/` directory, strict TypeScript, ESLint, Prettier, Vitest, React Testing Library, jsdom, and `@testing-library/jest-dom`.

The API uses the Python 3.14 release line and uv. Backend tooling is configured in `pyproject.toml` and includes Ruff, Pyright, pytest, and HTTPX-based FastAPI testing.

Runtime release lines are the current scaffold compatibility policy rather than a permanent architectural identity. Exact dependency versions are captured by application lockfiles.

The initial API exposes only `GET /health` as an external-dependency-free liveness check. The initial web page is only a minimal Investment Tracker scaffold.

Only modules required by working functionality are created. The logical `domain`, `application`, and `infrastructure` boundaries from Decision 006 remain in force but are not represented by empty packages. A composition root is not created until concrete wiring exists.

Playwright remains the approved end-to-end testing technology but is not initialized until an end-to-end test is needed.

No root package manager workspace or monorepo orchestration framework is introduced. Each application owns its dependencies, lockfile, commands, and checks.

**Reason**

The first scaffold establishes a small, reproducible development baseline for both approved runtimes and verifies that the web and API applications can be installed, started, linted, typechecked, formatted, and tested independently.

Keeping the scaffold minimal avoids speculative architecture and infrastructure while providing an executable foundation for future product work.

**Consequences**

Developers need both supported runtime release lines and the corresponding package managers.

Application changes must keep the relevant lint, typecheck, test, and format checks passing. Dependency lockfiles are committed for reproducible installation.

Application-code changes use short-lived branches and pull requests.

The physical backend structure will grow only when real use cases require the approved architectural layers. Database setup, migrations, Docker, authentication, financial features, and external integrations are not part of this scaffold.

---

## Decision 008 — Persistence foundation and first data model boundaries

**Decision**

The first Investment Tracker persistence model defines only the canonical accounting inputs and minimal identity boundaries required for subsequent portfolio state reconstruction.

Canonical persistence entities:

- Portfolio.
- InvestmentAccount.
- Instrument.
- Transaction.

Relationships:

```text
Portfolio 1:N InvestmentAccount

InvestmentAccount 1:N Transaction

Instrument 1:N Transaction
through nullable Transaction.instrument_id

Transaction 1:N Transaction
through nullable related_transaction_id
```

`related_transaction_id` is a nullable self-reference to an originating or related Transaction and allows one transaction to have several related transactions, such as separate FEE or TAX records.

The financial semantics of canonical transactions are defined by Decision F001 in `docs/CALCULATIONS.md`.

### Portfolio

Fields:

- `id` — BIGINT identity.
- `name` — required.
- `base_currency` — VARCHAR(3), required.
- `created_at` — TIMESTAMPTZ.
- `updated_at` — TIMESTAMPTZ.

At the initial stage, Portfolio does not contain:

- `user_id`.
- Soft delete.
- Status.

The absence of `user_id` corresponds to the single-user scope of the first version.

### InvestmentAccount

Fields:

- `id`.
- `portfolio_id`.
- `name`.
- `created_at`.
- `updated_at`.

At the initial stage, InvestmentAccount does not contain:

- Account currency.
- Account type.
- Broker identity.
- External broker ID.
- Status.

InvestmentAccount may be multi-currency.

The currency of a canonical transaction is stored on the Transaction itself rather than being determined by an account-level currency.

### Instrument

Initial fields:

- `id`.
- `name`.
- `created_at`.
- `updated_at`.

Instrument is present in the first schema to provide a stable internal identity for a financial instrument.

At this stage, Instrument does not contain:

- Ticker.
- ISIN.
- Exchange.
- Listing.
- Asset type.
- Currency.
- Broker identifiers.

Ticker is not treated as a globally unique instrument identity.

A richer instrument and reference-data model will be defined by a separate decision when a real need appears.

### Transaction

Fields:

- `id`.
- `account_id`.
- `instrument_id` — nullable.
- `related_transaction_id` — nullable.
- `type`.
- `quantity` — nullable.
- `price` — nullable.
- `cash_amount` — required.
- `currency_code` — required.
- `effective_date` — required.
- `settlement_date` — nullable.
- `note` — nullable.
- `created_at`.
- `updated_at`.

Supported v1 transaction types:

- `DEPOSIT`.
- `WITHDRAWAL`.
- `BUY`.
- `SELL`.
- `DIVIDEND`.
- `COUPON`.
- `FEE`.
- `TAX`.

Transaction type is stored as VARCHAR with a database constraint that permits only the approved v1 values.

PostgreSQL ENUM is not used for transaction type at this stage.

### Numeric policy

Persistence uses exact decimal representation.

`cash_amount`:

```text
NUMERIC(24,8)
```

`quantity`:

```text
NUMERIC(28,12)
```

`price`:

```text
NUMERIC(28,12)
```

Python-side representation:

```text
Decimal
```

Canonical financial values do not use binary floating point.

The selected storage precision defines the available storage precision but does not define financial rounding methodology.

Rounding rules must be approved separately where they are required by a specific financial methodology.

Canonical numeric magnitudes are non-negative according to Decision F001.

Transaction direction is determined by transaction `type`, not by the sign of a persisted amount or quantity.

### Database constraints

PostgreSQL must provide structural integrity, including:

- Primary keys.
- Foreign keys.
- Universal NOT NULL requirements.
- Approved transaction type values.
- Non-negative canonical numeric magnitudes.
- Structural formatting of currency codes.
- Prevention of a direct transaction self-reference through `related_transaction_id`.

Large transaction-type-specific conditional CHECK constraints are not introduced at the initial stage.

For example, the rule:

```text
BUY requires instrument / quantity / price
```

initially belongs to application and domain validation rather than a complex database CHECK expression.

Database constraints must protect universal structural invariants without prematurely encoding financial methodology that has not yet been approved.

### Foreign-key and delete policy

Foreign keys use conservative RESTRICT semantics.

Accounting history is not cascade-deleted.

In particular, a Transaction referenced through `related_transaction_id` must not automatically:

- Cascade-delete related records.
- Leave them silently detached through automatic nullification of the relationship.

Deletion and correction of canonical transactions are performed deliberately through application logic.

A stricter audit or reversal model may be introduced later through a separate decision.

### Time semantics

`effective_date` represents the financial or business date of a transaction.

For:

- `BUY`.
- `SELL`.

it is the trade or execution date.

For other types, it is the business-effective date of the corresponding event.

`settlement_date` is the nullable actual settlement date.

It is intended primarily for operations where settlement is a separate known fact.

The system must not derive a settlement date automatically through hardcoded T+1 or T+2 assumptions.

`created_at` and `updated_at` are UTC-aware persistence timestamps and describe the persistence lifecycle rather than financial effective time.

### Canonical source of truth

Persisted canonical facts:

- Portfolio metadata.
- InvestmentAccount metadata.
- Instrument identity.
- Transaction history.

The following values are derived state and are not an independent accounting source of truth:

- Cash balances.
- Positions.
- Lots.
- Cost basis.
- Average price.
- Realised P&L.
- Unrealised P&L.
- Portfolio value.
- Allocation.
- TWR.
- XIRR.
- Benchmark result.
- FX effect.

If caches, snapshots, or materialized derived state are introduced in the future, they must be rebuildable from canonical inputs and approved financial methodology.

### Local database direction

When persistence implementation begins, the initial local development direction is:

```text
Next.js    → host
FastAPI    → host
PostgreSQL → Docker Compose
```

This defines the direction of the next implementation step.

Docker Compose is not created as part of the Decision 008 documentation update itself.

### First persistence vertical slice

The first approved backend persistence slice is:

```text
Create Portfolio
→ Create InvestmentAccount
→ Create DEPOSIT Transaction
→ Read persisted data
```

This slice does not include:

- UI.
- BUY/SELL.
- P&L.
- Market data.

Instrument exists in the initial schema for stable internal identity, but separate Instrument CRUD is not required by the first vertical slice.

**Reason**

Investment Tracker uses transaction history as canonical accounting input, while portfolio state and financial metrics must be calculated from canonical facts.

The first persistence model must therefore preserve the minimal set of facts required for subsequent:

- Portfolio reconstruction.
- Calculation of positions.
- Cost-basis calculations.
- Cash-flow reconstruction.
- Realised and unrealised P&L.
- Performance calculations.
- Benchmark calculations.
- Future broker and import normalization.

At the same time, the schema must not prematurely design:

- Broker-specific identities.
- Instrument reference-data model.
- Account taxonomy.
- Derived portfolio state.
- Financial methodology that has not yet been approved.

Portfolio, InvestmentAccount, Instrument, and Transaction provide the minimal stable boundaries for the first persistence implementation.

The Transaction design relies on the approved Decision F001 — Canonical transaction semantics.

Financial semantics that have not yet been approved must not be invented at the database schema level.

**Consequences**

Transaction history becomes the canonical persistence foundation for accounting calculations.

Cash balances, positions, lots, cost basis, P&L, performance, and other portfolio metrics are not stored as an independent source of truth.

Canonical transaction values use unsigned or non-negative magnitudes and exact decimal representation.

Transaction direction is determined by `type`.

Fees and taxes may exist as separate related transactions through `related_transaction_id`.

Instrument identity exists from the first schema, while instrument metadata intentionally remains minimal.

The database provides universal structural integrity, while transaction-type-specific financial validation initially remains in domain and application logic.

Delete behavior is conservative and does not use cascade deletion of accounting history.

PostgreSQL, Docker, Alembic, and SQLAlchemy implementation remains a separate next step and is not part of this documentation change.

The first persistence implementation must be limited to the minimal vertical slice:

```text
Portfolio
→ InvestmentAccount
→ DEPOSIT Transaction
→ persisted read
```

without premature BUY/SELL, P&L, market data, or UI.
