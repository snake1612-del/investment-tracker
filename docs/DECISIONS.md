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

---

## Decision 009 — Persistence implementation, migrations and local database

**Decision**

Decision 008 определил canonical persistence model и первый persistence vertical slice.

Decision 009 определяет способ реализации этой модели: local PostgreSQL, SQLAlchemy infrastructure, Alembic migrations, transaction boundaries, repository/UoW contracts, первый persistence API и соответствующую test strategy.

Финансовая семантика canonical transactions остаётся определённой Decision F001 в `docs/CALCULATIONS.md`.

### Runtime architecture

Основное runtime/dependency direction:

```text
HTTP / FastAPI
→ Application use-case functions
→ framework-independent Domain where justified
→ application-facing Unit of Work / repository contracts
→ SQLAlchemy infrastructure
→ Psycopg 3 sync
→ PostgreSQL 18
```

Application layer не знает о SQLAlchemy `Session`.

SQLAlchemy infrastructure является implementation detail.

### Transaction ownership

Одна application use case определяет logical transaction boundary.

Для mutating use case:

```text
HTTP request
→ application use case
→ open Unit of Work
→ repository operations
→ application explicitly calls uow.commit()
→ close
```

При exception:

```text
rollback
→ close
```

Правила:

- repository implementations не вызывают `commit`;
- FastAPI routes не вызывают `commit`;
- concrete Unit of Work владеет SQLAlchemy Session mechanics;
- application use case определяет момент успешного commit;
- SQLAlchemy Session не передаётся в domain.

### Composition root

Теперь, когда появляется реальное persistence wiring, создаётся composition-root responsibility:

`app/bootstrap.py`

Composition root связывает concrete infrastructure с application/API dependencies, включая:

```text
configuration
→ engine/session factory
→ SqlAlchemyUnitOfWork factory
```

Это реализует ранее отложенную ответственность из Decision 006.

FastAPI routes не должны самостоятельно создавать SQLAlchemy Sessions или concrete repositories.

Отдельный dependency injection framework не используется.

`main.py` остаётся FastAPI entry point и не превращается в большой infrastructure wiring module.

### Local PostgreSQL

Local development использует PostgreSQL 18.

Architecture фиксирует PostgreSQL 18 major compatibility line.

Repository configuration при этом pin-ит конкретный поддерживаемый PostgreSQL 18 maintenance image.

Initial image:

```text
postgres:18.6
```

Не используются:

- `postgres:latest`;
- unpinned major-only image;
- PostgreSQL 19 beta/pre-release.

Maintenance update внутри PostgreSQL 18 является обычным reviewed dependency-maintenance change после прохождения tests и не требует нового architectural Decision.

Переход с PostgreSQL 18 на следующую major release является отдельным explicit upgrade task.

### Docker Compose

Docker Compose используется только для local PostgreSQL.

Initial Compose environment содержит один service:

```text
db
```

Он использует:

- PostgreSQL 18.6 initial pinned image;
- database `investment_tracker`;
- disposable local-development user `investment_tracker`;
- port `5432`;
- named volume `postgres_data`;
- `pg_isready` healthcheck;
- no automatic restart policy.

FastAPI и Next.js продолжают запускаться непосредственно на host.

Не добавляются:

- FastAPI container;
- Next.js container;
- pgAdmin;
- Adminer;
- Redis;
- reverse proxy;
- другие infrastructure services.

Disposable local-development credentials могут находиться в safe example/local-development configuration.

Production или real secrets никогда не commit-ятся.

### Environment configuration

Backend persistence configuration использует:

- `DATABASE_URL`;
- `TEST_DATABASE_URL`.

Ignored local file:

`apps/api/.env`

Committed example:

`apps/api/.env.example`

`.env.example` содержит только безопасные disposable local-development values.

Не добавляются:

- `pydantic-settings`;
- `python-dotenv`.

Используется небольшой stdlib-based configuration module.

Local development commands могут передавать `.env` через:

```text
uv run --env-file .env ...
```

Application runtime должен требовать только configuration, которая ему действительно нужна.

Обычный API startup не должен завершаться ошибкой только из-за отсутствия `TEST_DATABASE_URL`.

`TEST_DATABASE_URL` является test-specific configuration.

### SQLAlchemy

Используется SQLAlchemy 2.x в modern typed declarative style:

- `DeclarativeBase`;
- `Mapped`;
- `mapped_column`.

Persistence implementation является synchronous.

Не используется:

- `AsyncSession`;
- async PostgreSQL driver.

Session configuration:

- `autoflush=True`;
- `expire_on_commit=False`.

`infrastructure/db` владеет:

- Base / MetaData;
- ORM models;
- engine/session factory;
- repository implementations;
- concrete Unit of Work;
- SQLAlchemy-specific persistence behavior.

Пока существуют только четыре небольшие модели, они могут находиться вместе в:

`infrastructure/db/models.py`

Initial tables:

- `portfolios`;
- `investment_accounts`;
- `instruments`;
- `transactions`.

Не вводится one-file-per-model structure без конкретной необходимости.

### ORM boundary

SQLAlchemy ORM objects не должны выходить через repository contracts в:

- application;
- domain;
- API contracts.

Repository contracts предоставляют только небольшие application/domain-friendly records, values или results, действительно необходимые use cases.

Не создаются:

- mapper framework;
- duplicate hierarchy classes для каждого ORM model;
- generic persistence DTO framework.

Mapping выполняется явно и локально там, где он реально необходим.

### Canonical persistence model

Physical schema реализует Decision 008.

#### portfolios

- `id` — BIGINT identity;
- `name` — required;
- `base_currency` — VARCHAR(3), required;
- `created_at` — timezone-aware timestamp;
- `updated_at` — timezone-aware timestamp.

#### investment_accounts

- `id` — BIGINT identity;
- `portfolio_id` — required FK;
- `name` — required;
- `created_at`;
- `updated_at`.

#### instruments

- `id` — BIGINT identity;
- `name` — required;
- `created_at`;
- `updated_at`.

#### transactions

- `id` — BIGINT identity;
- `account_id` — required FK;
- `instrument_id` — nullable FK;
- `related_transaction_id` — nullable self-FK;
- `type` — VARCHAR constrained to approved v1 values;
- `quantity` — nullable `NUMERIC(28,12)`;
- `price` — nullable `NUMERIC(28,12)`;
- `cash_amount` — required `NUMERIC(24,8)`;
- `currency_code` — required;
- `effective_date` — required DATE;
- `settlement_date` — nullable DATE;
- `note` — nullable;
- `created_at`;
- `updated_at`.

Supported v1 types:

- `DEPOSIT`;
- `WITHDRAWAL`;
- `BUY`;
- `SELL`;
- `DIVIDEND`;
- `COUPON`;
- `FEE`;
- `TAX`.

Transaction type остаётся VARCHAR + CHECK constraint.

PostgreSQL ENUM не используется.

Canonical numeric magnitudes используют non-negative constraints согласно Decision 008/F001.

Database также обеспечивает:

- PKs;
- FKs;
- universal NOT NULL constraints;
- approved transaction types;
- currency structural format;
- no direct transaction self-reference;
- conservative RESTRICT delete behavior.

Большие transaction-type-specific CHECK expressions не вводятся.

### Numeric representation

Persistence использует PostgreSQL NUMERIC.

Python использует `Decimal`.

Canonical monetary/accounting quantities не преобразуются в binary floating point.

Storage precision не определяет финансовую rounding methodology.

### Timestamps

`created_at` и initial `updated_at` являются PostgreSQL server-generated timezone-aware timestamps.

Future changes to `updated_at` выполняются через explicit persistence/application mutation behavior.

Не вводятся:

- database triggers;
- SQLAlchemy event hooks;
- hidden timestamp update machinery.

### Alembic

Alembic располагается в:

- `apps/api/alembic.ini`;
- `apps/api/migrations/`.

Alembic использует:

- `Base.metadata`;
- `DATABASE_URL` из environment.

Credentials не хранятся в `alembic.ini`.

Schema creation/evolution выполняется migrations.

`Base.metadata.create_all()` не используется для:

- normal application bootstrap;
- normal integration-test schema creation.

Autogenerate может использоваться для создания candidate migration, но migration должна быть manually reviewed перед commit.

Migration, уже merged в shared `main` history, считается immutable.

Исправление shared schema выполняется новой migration.

Unmerged feature-branch migration может быть regenerated до merge.

Initial migration создаёт ровно четыре таблицы:

- `portfolios`;
- `investment_accounts`;
- `instruments`;
- `transactions`;

с constraints Decision 008.

Seed/demo data не добавляется.

### Database naming convention

SQLAlchemy MetaData использует naming convention для:

- primary keys;
- foreign keys;
- unique constraints;
- check constraints;
- indexes.

Convention:

```text
pk_%(table_name)s
fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s
uq_%(table_name)s_%(column_0_name)s
ck_%(table_name)s_%(constraint_name)s
ix_%(table_name)s_%(column_0_name)s
```

CHECK constraints получают короткие semantic names.

### Initial indexes

Первоначально создаются только индексы, для которых уже существует непосредственная use-case необходимость:

- `investment_accounts.portfolio_id`;
- `transactions.account_id`.

Nullable/future fields не индексируются заранее без конкретной query need.

### Repository policy

Generic Repository Pattern не используется.

Первый slice требует только следующих capabilities.

`PortfolioRepository`:

- `add`;
- `get`.

`InvestmentAccountRepository`:

- `add`;
- `get`.

`TransactionRepository`:

- `add`;
- `list_for_account`.

`InstrumentRepository` пока не вводится.

Также не создаются speculative methods/abstractions:

- `update`;
- `delete`;
- `list_all`;
- pagination;
- generic filtering;
- `BaseRepository`;
- `GenericRepository`;
- `RepositoryFactory`;
- `CRUDMixin`.

Concrete repositories используют SQLAlchemy Session, но никогда не выполняют `commit`.

### Unit of Work

Вводится один минимальный application-facing Unit of Work contract.

Это соответствует Decision 006: UoW появляется только теперь, когда существуют реальные mutating persistence use cases и transaction boundary.

Concrete `SqlAlchemyUnitOfWork` владеет:

- Session creation;
- concrete repositories;
- commit;
- rollback;
- close.

Application usage conceptually:

```python
with uow:
    ...
    uow.commit()
```

Не создаётся generic UoW framework или дополнительная hierarchy abstractions.

### Domain transaction validation

Transaction является первым persistence concept, для которого оправдана небольшая framework-independent domain representation.

Initial domain может содержать:

- `TransactionType`;
- небольшой `CanonicalTransaction` representation/value object;
- DEPOSIT factory/validation.

Не создаётся subtype hierarchy:

- `BuyTransaction`;
- `SellTransaction`;
- `DepositTransaction`;
- `FeeTransaction`;
- и аналогичные transaction subclasses.

Для первого slice DEPOSIT имеет правила:

- type = `DEPOSIT`;
- instrument отсутствует;
- related transaction отсутствует;
- quantity отсутствует;
- price отсутствует;
- `cash_amount > 0`;
- `currency_code` состоит ровно из трёх uppercase ASCII letters;
- `effective_date` required;
- `settlement_date` absent;
- note optional.

Existence account проверяется application orchestration, а не самим Transaction domain object.

Universal DB constraint для `cash_amount` остаётся:

```text
cash_amount >= 0
```

DEPOSIT-specific domain rule строже:

```text
cash_amount > 0
```

Decision 009 не вводит дополнительную currency-support methodology или currency whitelist.

### Application layer

Initial application layer использует typed use-case functions, а не отдельный service class на каждый endpoint.

Первоначально необходимы use cases примерно следующего уровня:

- `create_portfolio`;
- `create_investment_account`;
- `create_deposit`;
- `list_account_transactions`.

Service classes не создаются без реальной необходимости.

Application use cases работают через repository/UoW contracts и не знают о concrete SQLAlchemy implementations.

### Initial API

Первый persistence API ограничен:

```text
POST /portfolios

POST /portfolios/{portfolio_id}/accounts

POST /accounts/{account_id}/deposits

GET /accounts/{account_id}/transactions
```

Response status:

- create → `201`;
- read → `200`.

Known application outcomes:

- missing Portfolio → `404`;
- missing Account → `404`;
- invalid domain/application input → `422`;
- known persistence conflict → `409`.

Unexpected infrastructure failures не должны раскрывать raw SQLAlchemy/PostgreSQL error details клиенту.

Generic:

```text
POST /transactions
```

пока не создаётся.

Существующий:

```text
GET /health
```

сохраняется.

### Decimal and date API contract

Canonical Decimal values передаются через HTTP как JSON strings.

Direction:

```text
PostgreSQL NUMERIC
→ Python Decimal
→ JSON decimal string
→ TypeScript string
```

Canonical amounts не сериализуются как JSON floating-point numbers.

String representation должна сохранять exact decimal value, но Decision 009 не устанавливает cosmetic fixed-scale/trailing-zero formatting.

Например:

```text
"100000.00"
```

и:

```text
"100000.00000000"
```

могут представлять одно и то же exact canonical numeric value.

API tests не должны зависеть от cosmetic trailing-zero count, пока отдельное API-formatting решение не установит такое требование.

Dates:

```text
DATE → YYYY-MM-DD
```

Persistence timestamps:

- ISO 8601;
- timezone-aware;
- UTC.

### PostgreSQL driver

Используется Psycopg 3 в synchronous mode.

SQLAlchemy dialect:

```text
postgresql+psycopg
```

Dependency:

```text
psycopg[binary]
```

Не добавляются:

- `psycopg2`;
- `asyncpg`.

### Test PostgreSQL

Persistence integration/API tests используют real PostgreSQL.

Local PostgreSQL instance может содержать:

- development DB: `investment_tracker`;
- test DB: `investment_tracker_test`.

`TEST_DATABASE_URL` должен указывать исключительно на test database.

Test bootstrap обязан немедленно завершаться ошибкой, если `TEST_DATABASE_URL` resolves к той же database, что и `DATABASE_URL`.

Automated tests никогда не должны:

- truncate development DB;
- drop development DB;
- reset development DB.

Local test bootstrap должен:

1. проверить, что development и test URLs указывают на разные database names;
2. использовать local PostgreSQL maintenance/bootstrap connection;
3. создавать или пересоздавать только `investment_tracker_test`;
4. никогда не выполнять destructive database-level operation над `investment_tracker`;
5. применять к test database:

```text
alembic upgrade head
```

Для schema setup не используется `Base.metadata.create_all()`.

Tests не запускают Docker самостоятельно.

Prerequisite:

```text
docker compose up -d db
```

Testcontainers не используется.

Parallel database tests пока не требуются.

Между integration/API tests применяется простой deterministic cleanup test tables/identities.

Не вводится сложная nested-savepoint infrastructure без необходимости.

### Migration verification

Первый persistence PR должен проверить полный migration lifecycle.

Из пустой DB:

```text
alembic upgrade head
```

должен создать ожидаемую four-table schema.

Также проверяется:

```text
alembic downgrade base
alembic upgrade head
```

И:

```text
alembic check
```

не должен обнаруживать model/schema migration drift.

### Test coverage

Минимальное meaningful coverage:

Domain:

- valid Deposit;
- negative amount rejected;
- zero amount rejected;
- canonical Deposit не имеет instrument/settlement/relation.

Application with fake UoW/repositories:

- missing Account → NotFound;
- valid Deposit persists and commits;
- invalid Deposit does not commit.

DB integration:

```text
Portfolio
→ Account
→ Deposit
→ read transactions
```

Проверяются:

- BIGINT IDs;
- Decimal round-trip;
- DATE round-trip;
- foreign keys;
- ORM/persistence mapping.

API integration:

```text
POST Portfolio
→ POST Account
→ POST Deposit
→ GET account transactions
```

Также:

- nonexistent Portfolio → `404`;
- nonexistent Account → `404`;
- invalid Deposit → `422`.

Existing health test сохраняется.

Не создаются десятки trivial tests без дополнительной confidence value.

### Developer workflow

Expected local database workflow:

```text
docker compose up -d db
```

Backend:

```text
cd apps/api
uv sync
```

Local environment создаётся из committed `.env.example`.

Schema применяется через Alembic.

Unit tests могут выполняться без PostgreSQL.

Full persistence test suite выполняется после запуска local PostgreSQL.

README должен документировать только реально работающие команды, добавленные этим implementation.

### Dependencies

Новые dependencies ограничиваются concrete persistence need:

- SQLAlchemy 2.x;
- Alembic;
- `psycopg[binary]` 3.x.

Не добавляются:

- `pydantic-settings`;
- `python-dotenv`;
- testcontainers;
- factory-boy;
- faker;
- pytest-postgresql;
- SQLModel;
- dependency-injector.

### First implementation PR

Persistence foundation реализуется одним vertical-slice PR.

Scope:

- local PostgreSQL Compose service;
- environment policy;
- SQLAlchemy foundation;
- four ORM models;
- initial Alembic migration;
- minimal repositories;
- minimal Unit of Work;
- composition-root wiring;
- DEPOSIT domain validation;
- Create Portfolio;
- Create InvestmentAccount;
- Create Deposit;
- List Account Transactions;
- migration/integration/API tests;
- README local database workflow.

Workflow:

Issue:

`Implement initial persistence vertical slice`

Branch:

`feat/initial-persistence-slice`

Commit:

`feat: implement initial persistence vertical slice`

PR:

`Implement initial persistence vertical slice`

Application-code workflow остаётся:

```text
Issue
→ short-lived branch
→ implementation
→ checks/tests
→ commit
→ push
→ PR
→ review
→ merge
```

### Explicitly deferred

Decision 009 не реализует:

- BUY/SELL API;
- generic transaction creation;
- Instrument CRUD;
- FEE/TAX API;
- Dividend/Coupon API;
- FIFO/lots;
- realised P&L;
- unrealised P&L;
- fee → cost basis methodology;
- market data;
- FX methodology;
- tax calculation;
- broker integrations;
- imports;
- authentication;
- frontend/UI;
- cache/snapshots;
- async SQLAlchemy;
- Redis/Celery;
- background workers;
- production database hosting;
- cloud deployment;
- Kubernetes;
- CI/CD changes.

**Reason**

Decision 008 определил canonical persistence entities и source-of-truth boundary, но не определял implementation mechanics.

Первый persistence implementation должен сохранить framework-independent domain/application layers, обеспечить безопасные transaction boundaries и сделать schema evolution воспроизводимой через migrations.

SQLAlchemy 2.x и Psycopg 3 дают synchronous persistence foundation, совместимую с выбранным FastAPI backend без преждевременного async complexity.

Alembic становится единственным normal schema-evolution mechanism, чтобы physical database schema оставалась versioned и reviewable.

Minimal repositories и Unit of Work появляются только вместе с реальными persistence use cases и не превращаются в generic data-access framework.

Real PostgreSQL используется в integration/API persistence tests, потому что PostgreSQL-specific constraints, numeric behavior, foreign keys и migrations являются частью persistence correctness.

Первый vertical slice сознательно ограничен:

```text
Portfolio
→ InvestmentAccount
→ DEPOSIT
→ persisted read
```

чтобы проверить всю цепочку HTTP → application → domain → persistence → PostgreSQL без преждевременного введения BUY/SELL, P&L, market data или новой финансовой методологии.

**Consequences**

Project получает первый real persistence layer и local PostgreSQL development environment.

`infrastructure/db` физически появляется согласно boundaries Decision 006.

Минимальный application-facing Unit of Work становится transaction boundary между application и SQLAlchemy infrastructure.

FastAPI routes остаются thin и не получают SQLAlchemy Session или commit responsibility.

Schema создаётся и изменяется только через Alembic migrations.

Canonical Decimal values сохраняются как PostgreSQL NUMERIC / Python Decimal и пересекают HTTP boundary как JSON strings.

Integration/API persistence tests требуют запущенного local PostgreSQL, тогда как domain/application unit tests остаются независимыми от database.

Test database отделяется от development database и защищается fail-fast checks против destructive reset неправильной DB.

PostgreSQL 18 является текущей supported major line, а конкретный maintenance image pin остаётся обновляемой repository configuration.

Decision F001 остаётся единственным financial source of truth для canonical transaction semantics; Decision 009 не определяет FIFO, P&L, cost basis, FX или другую отложенную финансовую методологию.

## Decision 010 — Minimal Instrument and manual BUY / SELL vertical slice

**Decision**

The next backend-only vertical slice is:

```text
Instrument create/list
→ manual BUY / SELL
→ existing account transaction-history read
```

This slice does not introduce portfolio calculations or frontend UI.

Financial semantics for canonical trades remain defined by Decisions F001 and F002 in `docs/CALCULATIONS.md`.

### Instrument persistence model

The existing Instrument persistence model remains unchanged.

Fields remain:

- `id`;
- `name`;
- `created_at`;
- `updated_at`.

Decision 010 does NOT add:

- ticker;
- ISIN;
- FIGI;
- exchange;
- asset class;
- instrument currency;
- quotation metadata;
- provider identifiers;
- `portfolio_id`;
- `account_id`.

Instrument is global within the current single-user application.

It is not owned by a Portfolio or InvestmentAccount.

Decision 010 does not introduce:

- Instrument membership tables;
- holdings tables;
- watchlists;
- account-to-instrument pre-association.

Any existing global Instrument may be referenced by any existing InvestmentAccount transaction.

### Instrument name semantics

For manual Instrument creation:

- surrounding whitespace is trimmed;
- the resulting name is required;
- length must be between 1 and 200 characters inclusive;
- internal whitespace is preserved;
- Unicode is allowed.

Duplicate Instrument names are allowed.

Decision 010 does not define:

- case-sensitive uniqueness;
- case-insensitive uniqueness;
- canonical-name normalization;
- a UNIQUE constraint on Instrument name.

Instrument identity remains its internal `id`, not its name.

### No-schema-migration guardrail

Decision 010 requires no schema migration.

Before implementing this slice, Development must verify that the existing physical `Instrument.name` column can represent the approved application rule of 1..200 characters.

If the existing persistence capacity contradicts this requirement, implementation must stop and report the mismatch.

Development must not silently:

- add a migration;
- change the schema;
- weaken the approved application rule;
- change Decision 010.

Any required schema change must be decided explicitly before implementation continues.

### Instrument API

The minimal public Instrument API is:

```text
POST /instruments
GET /instruments
```

`POST /instruments`:

- creates an Instrument;
- returns `201`;
- returns the created Instrument.

`GET /instruments`:

- returns existing Instruments;
- uses deterministic `id ASC` ordering.

This slice does not require:

```text
GET /instruments/{id}
```

The public Instrument API does not include:

- search;
- autocomplete;
- pagination;
- filtering;
- reference-data synchronization.

### Instrument repository

Add an application-facing Instrument repository with only:

- `add`;
- `get`;
- `list`.

These capabilities are justified by current use cases:

- `add` → create Instrument;
- `get` → validate Instrument existence for BUY/SELL;
- `list` → minimal Instrument selection/read API.

The repository is exposed through the existing Unit of Work.

No generic repository abstraction is introduced.

### Manual BUY / SELL API

Manual BUY and SELL use separate explicit endpoints:

```text
POST /accounts/{account_id}/buys
POST /accounts/{account_id}/sells
```

Decision 010 does NOT introduce:

- generic `POST /transactions`;
- generic public `POST /trades`.

The endpoint determines transaction type.

`account_id` comes from the path.

Request does not contain:

- `type`;
- `account_id`;
- `related_transaction_id`;
- fee;
- tax.

For manual BUY/SELL created by this slice:

```text
related_transaction_id = null
```

### BUY / SELL request

Required fields:

- `instrument_id`;
- `quantity`;
- `price`;
- `cash_amount`;
- `currency_code`;
- `effective_date`.

Optional fields:

- `settlement_date`;
- `note`.

These rules are intentionally stricter than the general canonical persistence capability.

### Decimal and canonical validation

Manual BUY/SELL follows Decision F002.

Validation requires:

- `instrument_id` present;
- `quantity > 0`;
- `price > 0`;
- `cash_amount > 0`;
- `currency_code` exactly three uppercase ASCII letters;
- `effective_date` present;
- when `settlement_date` exists:
  `settlement_date >= effective_date`.

No supported-currency whitelist is introduced.

Historical/backdated `effective_date` values are allowed.

There is no current-date validation.

Canonical Decimal input and output cross HTTP as JSON strings.

Binary floating-point conversion must not be used.

Exact persistence representability must be enforced against:

```text
quantity    → NUMERIC(28,12)
price       → NUMERIC(28,12)
cash_amount → NUMERIC(24,8)
```

Values that cannot be represented exactly must be rejected.

The application must not silently:

- round;
- truncate;
- quantize-to-fit;
- convert through float.

Storage precision does not define:

- financial rounding;
- tick size;
- instrument precision;
- currency rounding.

### Independent factual trade inputs

For manual BUY/SELL:

- `quantity`;
- `price`;
- `cash_amount`;

remain independent factual inputs.

The application must never rewrite:

```text
cash_amount = quantity × price
```

If exact arithmetic produces:

```text
quantity × price != cash_amount
```

the trade remains valid.

The submitted `cash_amount` must remain unchanged.

Decision 010 does not introduce a reconciliation-warning mechanism.

It does not introduce:

- `warnings[]`;
- domain warning framework;
- events framework;
- reconciliation tolerance.

### Transaction response and history

Successful BUY or SELL creation returns:

```text
201
```

and uses the same canonical Transaction representation already used by:

```text
GET /accounts/{account_id}/transactions
```

Conceptually this representation includes:

- `id`;
- `account_id`;
- `instrument_id`;
- `related_transaction_id`;
- `type`;
- `quantity`;
- `price`;
- `cash_amount`;
- `currency_code`;
- `effective_date`;
- `settlement_date`;
- `note`;
- `created_at`;
- `updated_at`.

Decimal fields are serialized as JSON strings.

Dates use ISO:

```text
YYYY-MM-DD
```

No separate trade-history endpoint is added.

Existing account transaction history remains deterministically ordered by:

```text
id ASC
```

This ordering is only persistence-read ordering.

It does NOT establish financial chronology.

Financial chronology cannot be inferred from `id`, because historical/backdated transactions may be entered after newer transactions.

### Application use cases

Add explicit public application use cases:

- `create_instrument`;
- `list_instruments`;
- `create_buy`;
- `create_sell`.

Reuse the existing account transaction-history use case.

BUY and SELL remain explicit public application capabilities.

They may share private internal orchestration helpers where that reduces duplication.

Do not expose a generic public/application `create_trade` use case merely for deduplication.

### Domain

Continue using the existing framework-independent transaction concepts:

- `CanonicalTransaction`;
- `TransactionType`.

Do not introduce:

- `BuyTransaction`;
- `SellTransaction`;
- Trade hierarchy;
- transaction subtype inheritance.

Add type-specific BUY/SELL validation to the existing framework-independent domain.

Domain/canonical validation owns:

- required Instrument identity for a manual trade;
- positive `quantity`;
- positive `price`;
- positive `cash_amount`;
- exact `[A-Z]{3}` currency structure;
- exact Decimal representability;
- settlement-date ordering;
- independent factual quantity/price/cash values.

Application orchestration owns:

- Account existence;
- Instrument existence.

Existence checks use repositories.

SQLAlchemy ORM relationships or objects must not leak into domain logic.

### Account ↔ Instrument relationship

Decision 010 introduces no Account-to-Instrument pre-association.

Any global Instrument may be referenced by any existing InvestmentAccount.

No additional relationship is created for:

- holdings;
- allowed instruments;
- portfolio membership;
- watchlists;
- instrument ownership.

Positions remain derived state from canonical transactions.

### SELL and derived state

Manual SELL creation does not consult reconstructed positions.

This slice contains:

- no position lookup;
- no oversell validation;
- no oversell warning;
- no position engine.

A SELL is not rejected merely because its quantity would exceed currently reconstructed position.

This follows Decision F002 and does not establish short-selling methodology.

Derived-state infrastructure must not be introduced merely to create canonical trades.

### FEE / TAX

FEE and TAX creation are not part of this slice.

Do not introduce:

- FEE endpoint;
- TAX endpoint;
- combined trade + fee workflow;
- combined trade + tax workflow.

FEE and TAX remain separate future canonical Transactions according to Decisions F001/F002.

Decision 010 does not define fee → cost basis or tax methodology.

### Persistence

No migration is expected.

Reuse the existing persistence model:

- Instrument table;
- Transaction table;
- existing BUY/SELL transaction type values;
- `instrument_id`;
- `quantity`;
- `price`;
- `cash_amount`;
- `currency_code`;
- effective/settlement date columns;
- existing foreign keys and universal constraints.

Application/domain rules remain intentionally stricter than the general persistence schema.

No schema redesign is introduced by Decision 010.

### Errors

Reuse the existing minimal application/API error conventions.

Return `404` for:

- Account not found;
- Instrument not found.

Return `422` for invalid input including:

- blank Instrument name;
- Instrument name longer than 200 characters;
- non-positive quantity;
- non-positive price;
- non-positive cash amount;
- invalid currency format;
- settlement before effective date;
- invalid decimal syntax;
- Decimal value not exactly representable in canonical persistence precision.

Unexpected infrastructure details must not leak through API responses.

Decision 010 does not introduce a new persistence-conflict model.

If an already existing application persistence-conflict outcome genuinely applies, its existing `409` mapping may continue to be used.

Duplicate Instrument names are explicitly allowed and must not produce `409`.

### Tests

Minimum meaningful coverage for this slice includes the following.

Instrument domain/application behavior:

- valid name accepted;
- surrounding whitespace trimmed;
- blank-after-trim rejected;
- name longer than 200 characters rejected;
- duplicate name semantics accepted.

BUY/SELL domain:

- valid BUY;
- valid SELL;
- non-positive quantity rejected;
- non-positive price rejected;
- non-positive cash amount rejected;
- invalid/lowercase currency rejected;
- settlement before effective date rejected;
- missing settlement accepted;
- historical effective date accepted;
- exact Decimal representability enforced;
- quantity/price/cash mismatch accepted;
- submitted `cash_amount` preserved;
- no position/oversell validation.

Application:

- create Instrument;
- list Instruments;
- missing Account;
- missing Instrument;
- successful BUY;
- successful SELL;
- successful mutating use case commits exactly once;
- failed use case does not commit.

Persistence/integration:

- Instrument add/get/list;
- deterministic Instrument `id ASC` list;
- BUY/SELL persistence and read-back;
- foreign-key behavior;
- exact Decimal round-trip;
- optional settlement date.

API:

- create Instrument;
- list Instruments;
- create BUY;
- create SELL;
- account transaction history exposes canonical trade facts;
- Decimal fields are strings;
- dates serialize correctly;
- relevant `404` and `422` outcomes;
- quantity/price/cash mismatch accepted;
- backdated trade accepted.

No portfolio golden tests are added because Decision 010 introduces no portfolio calculation methodology or engine behavior.

### Explicit non-scope

Decision 010 does NOT introduce:

- ticker;
- ISIN;
- FIGI;
- exchange/listing model;
- asset class;
- instrument/reference-data master system;
- instrument currency;
- quotation metadata;
- provider identifiers;
- Instrument search/autocomplete/pagination;
- holdings;
- watchlists;
- generic transaction API;
- generic public trade API;
- FEE/TAX creation;
- reconciliation-warning framework;
- positions;
- oversell validation;
- short-selling methodology;
- FIFO;
- lots;
- average cost;
- cost basis;
- realised P&L;
- unrealised P&L;
- fee → cost basis methodology;
- tax methodology;
- market data;
- FX;
- bond quotation semantics;
- accrued interest;
- settlement accounting engine;
- orders/executions/partial fills;
- corporate actions;
- broker imports;
- portfolio performance;
- TWR/XIRR;
- benchmarks;
- frontend trade UI;
- authentication;
- multi-user ownership;
- schema redesign.

**Reason**

Decision 008 intentionally introduced Instrument as a minimal stable internal identity before requiring a complete reference-data model.

Decision 009 implemented persistence around canonical transactions but deliberately stopped at DEPOSIT and did not provide Instrument creation/read workflow.

Decision F002 now defines the financial semantics required for manual BUY/SELL.

The smallest coherent next slice therefore needs only:

```text
minimal Instrument creation/read
→ explicit manual BUY/SELL entry
→ existing canonical transaction-history read
```

A richer Instrument model is not required to record trades for instruments that are correctly representable by a direct monetary unit price.

Keeping Instrument global to the current single-user application avoids inventing unnecessary ownership or membership models.

Separate BUY and SELL endpoints/use cases keep transaction intent explicit and avoid prematurely exposing a generic transaction/trade creation interface.

The slice intentionally does not depend on reconstructed position, reconciliation warnings, portfolio calculation logic, FEE/TAX creation, or reference-data infrastructure.

This preserves the project's pattern of introducing only abstractions and functionality required by the current vertical slice.

**Consequences**

The backend gains a minimal Instrument creation/list workflow and can record canonical manual BUY and SELL transactions according to Decision F002.

Instrument persistence remains intentionally minimal and unchanged.

Duplicate Instrument names remain valid; internal `id` is the stable identity.

Any existing global Instrument can be used by any existing InvestmentAccount.

Manual BUY/SELL application/domain validation becomes stricter than the general persistence schema.

Canonical quantity, price and cash amount remain independent exact Decimal facts.

BUY/SELL persistence does not depend on positions, cost basis, P&L or other derived state.

Existing account transaction history becomes the read surface for DEPOSIT, BUY and SELL canonical records, using deterministic `id ASC` persistence ordering without treating that ordering as financial chronology.

No schema migration is expected. If existing physical Instrument-name capacity cannot support the approved 1..200 rule, implementation must stop for a new architecture/schema decision instead of silently changing persistence.

Decision 010 adds no new financial methodology beyond Decisions F001/F002 and leaves portfolio calculations, richer instrument metadata, FEE/TAX creation and all other deferred areas unresolved.
