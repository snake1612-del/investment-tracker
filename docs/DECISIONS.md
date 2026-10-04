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

## Decision 011 — Account position quantity read slice

**Decision**

The next coherent feature slice records Decision F003 in `docs/CALCULATIONS.md` and implements pure Account position quantity reconstruction with one public endpoint:

```text
GET /accounts/{account_id}/positions
```

Position quantity follows Decision F003. The framework-independent domain calculation accepts canonical transactions and an explicit `as_of_date`, groups all Instruments in one pass, and does not read the system clock.

For this current-position endpoint, the application determines the current UTC calendar date once per request and passes it to the domain. No Clock abstraction, public `as_of` query parameter, or historical endpoint is introduced.

The read-only application use case checks Account existence, loads existing canonical transaction history through `TransactionRepository.list_for_account`, maps persistence-facing records to the domain's existing `CanonicalTransaction` representation, reconstructs quantities, omits zero results, preserves negative results, loads Instrument metadata once, and returns positions ordered by `instrument_id ASC`. It does not commit.

Instrument ID is the position identity; name is display metadata. Missing metadata for a non-zero reconstructed position is an internal data-integrity error, not an empty name or silently omitted position.

For an existing Account, the endpoint returns `200` and a list containing only:

- `instrument_id`;
- `instrument_name`;
- `quantity` as an exact-value JSON decimal string.

An Account with no non-zero positions returns `200` and `[]`. A missing Account returns `404`. Malformed canonical history is an internal error, not an input-validation `422`; raw infrastructure details are not exposed.

Transaction history remains factual input, and the domain applies the `effective_date <= as_of_date` filter. No SQL position aggregation, date-filtered repository method, position repository, position table, snapshot, materialized view, cache, derived column, or migration is introduced.

This slice does not add Portfolio positions, frontend UI, price or cash calculations, cost basis, P&L, market value, allocation, FX, performance, settlement accounting, short-selling classification, or FEE/TAX feature work.

**Reason**

Decisions F001/F002 and 008–010 establish canonical BUY/SELL facts and Instrument identity. Decision F003 now approves the minimal quantity methodology needed to reconstruct positions from those facts without inventing cost-basis, valuation, or short-selling rules.

Keeping calculation in the domain and using the existing factual-history repository preserves the financial boundary and makes historical-date behavior testable even though the first public endpoint shows only the current UTC-date view.

**Consequences**

Account position quantities are computed on read from canonical history and can be recomputed after corrections. Zero positions are omitted from the public response; negative quantities remain visible unchanged. The endpoint reports quantities only, without implying valuation or a complete short-selling methodology. Existing schema and repository contracts remain unchanged.

## Decision 012 — Portfolio position quantity read slice

**Decision**

Extend the Positions / Holdings foundation with one current-position endpoint:

```text
GET /portfolios/{portfolio_id}/positions
```

This endpoint uses the same position-item contract as `GET /accounts/{account_id}/positions`: `instrument_id`, `instrument_name`, and exact-value decimal-string `quantity`, ordered by `instrument_id ASC`. It exposes no Account breakdown or additional financial fields. There is no public `as_of` parameter or historical Portfolio endpoint.

Portfolio position quantity follows Decision F003 without a second financial calculation. For an existing Portfolio, the application:

1. Lists only its InvestmentAccounts in deterministic `id ASC` order through one new `InvestmentAccountRepository.list_for_portfolio(portfolio_id)` operation.
2. Determines one current UTC calendar date for the whole request.
3. Reads canonical transactions for each listed Account using the existing `TransactionRepository.list_for_account(account_id)` operation.
4. Maps all records to the same domain `CanonicalTransaction` input used by Account positions and calls `reconstruct_positions` exactly once for the combined history and evaluation date.
5. Omits final zero quantities, preserves negative quantities, loads Instrument metadata once, attaches names by Instrument ID, and sorts results by Instrument ID.

The application does not sum Account Decimal position results. The existing exact scaled-integer aggregation provides cross-Account totals without depending on the ambient Decimal context. Instrument names are display metadata, not aggregation identity; duplicate names remain separate by ID. Missing metadata for a non-zero position is an internal data-integrity failure.

The use case is read-only and does not commit. A missing Portfolio returns `404`. An existing Portfolio with no Accounts, no trades, or only final zero quantities returns `200` and `[]`. Negative results are returned unchanged, without warning, rejection, clamping, or short-selling classification. Malformed canonical history remains an internal error rather than a client-input `422`.

The accepted v1 data-access pattern is one Portfolio lookup, one Account list, one transaction-history read per Account, and one Instrument list. Transactions outside the requested Portfolio's Accounts never participate. No Portfolio transaction repository method, SQL position aggregation, position repository, materialized state, cache, derived column, or migration is introduced.

This decision does not add Portfolio history, Account breakdown, valuation, cost basis, P&L, allocation, FX, performance, settled/unsettled positions, FEE/TAX features, frontend UI, broker imports, or authentication.

**Reason**

Decision F003 already defines exact position quantity reconstruction independently of account count. Combining the canonical histories of a Portfolio's Accounts before one domain calculation gives the approved Portfolio total while preserving Account/Portfolio isolation and avoiding a second arithmetic path. The existing repository boundaries are sufficient with only the Account-list operation.

**Consequences**

Portfolio quantities are recomputed on read from canonical transactions and may be negative. Final zero positions are omitted from the public response. The endpoint shares Account position item semantics and remains quantity-only; it does not imply valuation or short-selling accounting. Persistence schema and financial methodology beyond F003 remain unchanged.

## Decision 013 — FIFO lots and cost-basis foundation

**Decision**

The FIFO Lots / Cost Basis foundation milestone will implement Decision F004 as framework-independent, recomputable derived financial state over canonical transaction history.

The milestone will introduce:

- exact FIFO lot reconstruction;
- AcquisitionLot results;
- DisposalMatch results;
- UnmatchedSell results;
- Account-level long cost-basis summaries;
- Portfolio-level long cost-basis aggregation;
- golden/reference and invariant tests.

It will not persist derived lots or cost basis and will not expose a new public monetary cost-basis or lots API.

### Reconstruction input

The existing `CanonicalTransaction` domain type is not the FIFO reconstruction input because F004 requires stable persisted transaction identity for same-day ordering.

A dedicated immutable framework-independent input:

`LotTransactionFact`

will contain only the canonical facts required by F004, including conceptually:

- transaction_id;
- account_id;
- transaction type;
- instrument_id;
- quantity;
- cash_amount;
- currency_code;
- effective_date.

Application code explicitly maps persistence-facing transaction records into this domain input.

SQLAlchemy objects and application records do not cross into the FIFO domain engine.

### Reconstruction boundary

FIFO reconstruction operates on exactly one InvestmentAccount at a time.

Conceptually:

`reconstruct_fifo_lots(account_transaction_facts) → FifoReconstruction`

The engine groups relevant transactions by canonical `instrument_id` internally.

It rejects input containing multiple Account identities.

Portfolio FIFO is never performed over combined Account histories.

### Financial ordering

The domain engine owns F004 chronology.

For each Account + Instrument stream, BUY and SELL transactions are processed by:

1. `effective_date ASC`;
2. `transaction_id ASC`.

Repository ordering has no financial meaning.

No transaction-type priority is applied for same-day events.

A same-day SELL whose transaction ID precedes a BUY remains unmatched if no earlier long lot exists; the later BUY does not retroactively resolve it.

### Quantity arithmetic

FIFO quantity calculations reuse the exact scale-12 integer representation already established for position reconstruction.

Canonical Decimal quantities are converted exactly into integer units of `10^-12`.

All lot matching, remaining quantities and unmatched quantities are calculated with arbitrary-precision integer arithmetic.

No Decimal-context-dependent quantity arithmetic is used.

The small existing scaled-integer conversion primitives may be extracted into a shared module within `domain/portfolio/engine` for reuse by both position and FIFO reconstruction.

### Exact acquisition basis

F004 monetary basis uses exact rational arithmetic.

The internal rational representation will use Python arbitrary-precision `Fraction` wrapped by a small immutable domain value conceptually named:

`ExactMoney`

containing:

- exact rational amount;
- currency_code.

The wrapper prevents arithmetic between different currencies unless they are explicitly kept in separate currency partitions.

No automatic FX conversion exists.

Canonical `cash_amount` is converted context-independently into exact scale-8 integer units and then into a rational major-currency amount.

Partial basis allocation uses integer quantity ratios and rational money:

`removed_basis = original_basis × matched_quantity_units / original_quantity_units`

Remaining basis is calculated exactly from the original lot:

`remaining_basis = original_basis × remaining_quantity_units / original_quantity_units`

No monetary rounding, truncation or finite Decimal approximation is introduced during reconstruction.

### Acquisition lots

Each canonical BUY creates one distinct derived AcquisitionLot.

The lot contains conceptually:

- source BUY transaction ID;
- instrument ID;
- acquisition effective date;
- original quantity;
- remaining quantity;
- original ExactMoney basis;
- remaining ExactMoney basis.

All lots, including fully closed lots, remain in the reconstruction result.

Open lots are a derived view of lots whose remaining quantity is positive.

BUY lots are never automatically merged.

### Disposal matches

A derived DisposalMatch contains conceptually:

- source SELL transaction ID;
- source BUY transaction ID;
- instrument ID;
- matched quantity;
- exact removed acquisition basis.

One SELL may produce several matches and one BUY lot may participate in several SELL matches.

Disposal matches are not persisted.

### Unmatched SELLs

If a SELL exceeds available preceding long lots, the excess becomes a derived UnmatchedSell.

It contains conceptually:

- source SELL transaction ID;
- instrument ID;
- effective date;
- unmatched quantity.

It has no monetary acquisition basis.

A later BUY, including a later BUY on the same effective date, does not retroactively resolve an earlier unmatched SELL.

### Reconstruction result

One Account reconstruction contains:

- account identity;
- all acquisition lots;
- disposal matches;
- unmatched sells.

`is_fully_resolved` is derived from the absence of unmatched SELLs rather than stored independently.

Account summaries and open-lot views are derived from the reconstruction rather than duplicated as authoritative state.

### Account summary

For each Account + Instrument, F004 can derive:

- open_long_quantity;
- remaining acquisition basis partitioned by currency;
- unmatched_sell_quantity.

Resolution status is derived from unmatched quantity.

`open_long_quantity` is an F004 long-lot concept and is not interchangeable with the F003 net position quantity.

In incomplete or oversold history the two may differ intentionally.

### Portfolio aggregation

Portfolio FIFO is performed separately for every InvestmentAccount.

Only after Account reconstruction are summaries aggregated by canonical `instrument_id`.

Portfolio remaining acquisition basis is summed separately for each currency.

No basis values in different currencies are combined.

Unmatched SELL quantities remain unresolved at the Account boundary and are aggregated only as unresolved quantities.

Long lots in one Account must never resolve or offset an unmatched SELL in another Account.

A Portfolio is not considered fully resolved if any contributing Account reconstruction remains unresolved.

### Transaction-type safety

The FIFO engine explicitly handles all currently known canonical TransactionTypes.

BUY and SELL have lot effects.

Current other canonical types:

- DEPOSIT;
- WITHDRAWAL;
- DIVIDEND;
- COUPON;
- FEE;
- TAX.

have explicitly defined no-lot effect under F004.

There is no generic fallback that silently ignores future transaction types.

A future canonical type that may affect quantity or basis requires an explicit financial-methodology decision before FIFO reconstruction accepts it.

Malformed required BUY/SELL reconstruction facts cause explicit domain failure and are never silently skipped or repaired.

### Persistence

Canonical transaction history remains the sole persisted source of truth.

The milestone introduces:

- no Lot table;
- no DisposalMatch table;
- no CostBasis table;
- no materialized view;
- no cache;
- no migration.

Create, edit, delete and backdated changes to canonical transaction history are reflected through full reconstruction on subsequent reads.

No incremental lot ledger becomes authoritative.

### Data access

Existing transaction-history repository contracts remain sufficient.

Account reconstruction uses the existing Account transaction-history read.

Portfolio reconstruction lists Accounts belonging to the Portfolio and reconstructs every Account independently before aggregation.

No specialized SQL FIFO query or additional persistence projection is introduced.

### Public API

No new public cost-basis or lot endpoint is introduced in this milestone.

F004 permits exact rational monetary values such as `100/3`, while presentation rounding and long-term HTTP representation have not yet been approved.

The architecture will not expose a finite Decimal approximation and will not prematurely make a numerator/denominator representation part of the public API contract.

Existing quantity-position APIs remain unchanged.

### Testing

F004 is considered incomplete without both ordinary domain tests and normative golden/reference tests.

Golden tests will cover representative approved FIFO cases including open lots, partial disposal, multiple lots, fractional quantities, repeating rational basis, same-date transaction-ID ordering, backdated history, oversells, SELL-only history, Account isolation, mixed currencies, ignored FEE, full-disposal invariants and differing SELL currency.

Invariant tests must verify exactly:

`original quantity = disposed quantity + remaining quantity`

and:

`original basis = removed basis + remaining basis`

with no tolerance or rounding.

Tests must also demonstrate independence from Python Decimal context precision.

Focused PostgreSQL/application integration tests must verify that persisted transaction identity and canonical facts are mapped correctly into FIFO reconstruction, including same-date ordering and Account isolation.

**Reason**

F004 requires stateful FIFO reconstruction, stable persisted transaction identity and exact rational monetary allocation that are not required by the existing position-quantity engine.

A dedicated FIFO reconstruction input preserves the existing CanonicalTransaction boundary while supplying the persisted transaction ID required for deterministic same-day ordering.

Running reconstruction one Account at a time structurally enforces the no-cross-account FIFO rule.

Using exact scaled integers for quantities and Fraction-backed currency-safe money eliminates Decimal-context rounding and preserves repeating acquisition-basis fractions exactly.

Keeping derived lots, matches and basis recomputable avoids introducing authoritative state that could drift after editable or backdated canonical history changes.

Deferring public monetary APIs prevents architecture from inventing presentation rounding or prematurely exposing an internal rational wire representation.

**Consequences**

Investment Tracker gains a complete exact long-position FIFO and acquisition-cost foundation without yet implementing P&L or valuation.

The domain will contain a dedicated FIFO input and exact-money representation in addition to the existing canonical transaction and position models.

Account F004 open-long quantity may differ from F003 net position quantity when canonical history contains unmatched SELLs; both concepts remain distinct.

Portfolio basis is aggregated only after independent Account reconstruction and remains partitioned by currency.

Financial reconstruction remains more computationally expensive than persisted projections because it sorts and rebuilds history on demand, but this is accepted for current single-user scale.

No new HTTP endpoint, schema migration or derived persistence is introduced.

A later product/API decision will be required before exact cost basis is exposed to clients, because presentation rounding and long-term wire representation remain intentionally unresolved.

## Decision 014 — Gross trade-cash realised P&L foundation

**Decision**

The Gross Realised P&L foundation milestone will implement Decision F005 as framework-independent, recomputable derived financial state over the authoritative F004 FIFO reconstruction and canonical SELL facts.

F004 remains the sole source of truth for BUY-lot matching and removed acquisition basis.

F005 will not implement or duplicate FIFO matching.

### Reconstruction boundary

Gross realised P&L reconstruction will conceptually accept:

`FifoReconstruction + the LotTransactionFact collection used to produce it`

and return an Account-level gross realised P&L reconstruction.

Existing `LotTransactionFact` is sufficient because it contains the SELL transaction identity, Account and Instrument identity, quantity, cash amount, currency and effective date required by F005.

No new F005 transaction-fact type will be introduced.

Application code will load Account canonical history once, map it to `LotTransactionFact` once, perform F004 reconstruction once and then perform F005 reconstruction from those same facts and the resulting FIFO reconstruction.

### SELL lookup

F005 will build an in-memory transaction-ID lookup from supplied facts.

Each `DisposalMatch` and `UnmatchedSell` produced by F004 must reference an existing supplied fact whose type is exactly `SELL`.

No repository lookup is performed per match.

Duplicate or missing factual transaction identities are reconstruction errors.

### Exact proceeds

Canonical `SELL.cash_amount` is the authoritative total trade proceeds.

SELL price is factual metadata and does not determine F005 proceeds.

Canonical cash amounts are converted exactly through the existing context-independent scale-8 integer conversion and represented using the existing Fraction-backed `ExactMoney` type in the SELL currency.

For a SELL with total quantity `Q`, total proceeds `P` and component quantity `q`, component proceeds are calculated exactly as:

`P × q / Q`

using integer quantity ratios and rational arithmetic.

Every matched and unmatched SELL component receives its independently calculated share of the original SELL proceeds.

No progressive subtraction, remainder correction, Decimal division or monetary rounding is used.

### ExactMoney

The existing `ExactMoney` domain type remains the only exact rational monetary representation used by F004 and F005.

It will gain the minimum same-currency subtraction operation required for realised P&L.

Subtracting values with different currency codes remains invalid.

No automatic FX conversion is introduced.

### RealisedMatch

Each authoritative F004 `DisposalMatch` produces one immutable F005 `RealisedMatch` containing conceptually:

- source SELL transaction ID;
- source BUY transaction ID;
- instrument ID;
- matched quantity;
- allocated SELL proceeds;
- removed acquisition basis.

If allocated proceeds and removed basis use the same currency, exact gross trade-cash realised P&L is derived as:

`allocated proceeds - removed acquisition basis`

If their currencies differ, numeric P&L is unresolved.

Both exact monetary legs remain preserved.

A separate stored resolved-status flag is not required.

### Unresolved reasons

F005 distinguishes at least:

- `MISSING_ACQUISITION_BASIS`
- `CURRENCY_MISMATCH`

Currency mismatch applies to a matched component whose proceeds and removed basis currencies differ.

Missing acquisition basis applies to an unmatched SELL component.

Unresolved state is never represented as zero P&L.

### UnmatchedProceeds

Every authoritative F004 unmatched SELL quantity produces an immutable `UnmatchedProceeds` component containing conceptually:

- source SELL transaction ID;
- instrument ID;
- unmatched quantity;
- allocated factual SELL proceeds.

No acquisition basis and no numeric realised P&L are assigned.

Its unresolved reason is missing acquisition basis.

### SELL-level reconstruction

F005 groups derived components by source SELL.

A derived SELL result contains conceptually:

- SELL transaction ID;
- instrument ID;
- SELL effective date;
- total factual ExactMoney proceeds;
- matched RealisedMatch components;
- optional unmatched proceeds component.

This boundary preserves the per-SELL proceeds-conservation invariant and permits one SELL to contain resolved, currency-mismatch-unresolved and missing-basis-unresolved components simultaneously.

SELL realisation date is always `SELL.effective_date`.

Settlement date does not control F005 recognition.

### Conservation and integrity

For every SELL, F005 must verify exactly:

`sum matched quantities + unmatched quantity = SELL quantity`

and:

`sum all allocated component proceeds = SELL factual cash amount`

No tolerance or rounding is permitted.

For a fully matched SELL whose removed acquisition basis is entirely in the SELL proceeds currency:

`sum component realised P&L = SELL proceeds - sum removed acquisition basis`

exactly.

Any violation is an internal reconstruction failure.

F005 must not silently renormalize malformed F004 output or canonical facts.

### Account reconstruction and summary

One Account gross realised-P&L reconstruction contains all derived SELL results for that Account.

An Account summary derives:

- resolved P&L partitioned by currency;
- explicit unresolved components.

Only resolved components contribute to resolved P&L subtotals.

`is_fully_resolved` is derived from the absence of unresolved components.

Resolved subtotal fields must be named and treated explicitly as resolved P&L and must not masquerade as complete total P&L when unresolved components exist.

No separate per-Instrument summary is required in this milestone because component and SELL results retain canonical Instrument identity and can be projected later if needed.

### Portfolio aggregation

Portfolio F005 aggregation occurs only after each InvestmentAccount has independently completed F004 and F005 reconstruction.

Resolved Account P&L values are summed only within the same currency.

Currencies are never combined without an explicit future FX methodology.

Unresolved components remain unresolved and retain their Account/source identity.

Resolved P&L in one Account cannot offset, resolve or conceal an unresolved component in another Account.

Portfolio resolution status is derived from the resolution status of all contributing Account results.

### Transaction-type safety

F005 relies on F004 as the authoritative exhaustive canonical transaction-type matching boundary.

F005 processes only SELL transactions referenced by authoritative F004 disposal or unmatched components.

Every such reference must resolve to a canonical SELL fact.

F005 does not traverse or allocate FEE or TAX records.

FEE and TAX have no effect on gross trade-cash realised P&L.

A future disposal-like transaction type requires explicit financial-methodology support rather than being silently treated as a realised-P&L zero event.

### Persistence and recomputation

Canonical transaction history remains the persisted source of truth.

The milestone introduces:

- no realised P&L table;
- no realised-match table;
- no proceeds-allocation table;
- no materialized view;
- no cache;
- no migration.

F004 and F005 are recomputed from current canonical history.

Backdated create, edit and delete operations affect subsequent results through full reconstruction.

No incremental realised-P&L ledger becomes authoritative.

### Data access

Existing persistence contracts remain sufficient.

Account reconstruction uses the existing Account transaction-history read.

Portfolio reconstruction lists Accounts belonging to the Portfolio and reconstructs F004 and F005 independently for each Account before aggregation.

No P&L repository, SQL P&L calculation, match repository or proceeds-allocation query is introduced.

Account application orchestration must avoid loading the same history separately for F004 and F005.

### Public API

No new public gross realised-P&L endpoint is introduced in this milestone.

F005 produces exact rational monetary results, potentially across multiple currencies and with partially unresolved states.

Presentation rounding and a stable long-term wire representation for exact rational and unresolved monetary results have not yet been approved.

The architecture therefore will not expose rounded Decimal approximations or make an internal numerator/denominator representation part of the public API contract prematurely.

### Testing

F005 is incomplete without ordinary domain/invariant tests, normative golden/reference tests and focused real-PostgreSQL integration tests.

Tests must verify exact proceeds conservation, exact same-currency P&L subtraction, partial unresolved results, currency mismatch, missing acquisition basis, Account isolation, Portfolio currency partitioning, FEE/TAX exclusion, backdated history and Decimal-context independence.

Golden expected monetary values use exact `ExactMoney`/Fraction equality rather than rounded Decimal approximations.

Existing F003 position and F004 FIFO/cost-basis test suites must remain green.

**Reason**

F004 already provides the authoritative mapping from SELL quantities to acquisition lots and exact removed acquisition basis.

Reusing that reconstruction avoids creating competing FIFO implementations or inconsistent cost-basis logic.

F005 adds only the missing economic leg: exact factual SELL proceeds allocated proportionally across the F004 matched and unmatched quantities.

The existing Fraction-backed `ExactMoney` representation already provides the required exact rational monetary foundation and currency protection, so a second monetary representation is unnecessary.

Grouping output by SELL makes proceeds conservation, realisation date and partial resolution directly auditable.

Keeping unresolved reasons explicit prevents missing basis or FX requirements from being silently interpreted as zero realised P&L.

Deferring the public API avoids inventing presentation rounding or prematurely exposing internal rational representation as a long-lived contract.

**Consequences**

Investment Tracker gains exact gross trade-cash realised P&L reconstruction for matched long-position disposals.

One SELL may contain a combination of resolved and unresolved components.

Resolved P&L remains partitioned by currency and unresolved components remain explicit.

SELL price, FEE and TAX do not influence F005 results.

Portfolio realised P&L is aggregated only after independent Account reconstruction.

F005 remains recomputable from canonical transaction history and introduces no database schema change or derived-state persistence.

A future product/API decision will be required before realised P&L is publicly exposed because rounding, exact rational wire representation and unresolved-state presentation remain intentionally undecided.

## Decision 015 — Realised P&L public read contract

**Decision**

The Gross Realised P&L milestone will expose the F005 gross trade-cash realised P&L reconstruction through lossless Account and Portfolio read APIs.

The public endpoints are:

GET /accounts/{account_id}/realised-pnl

GET /portfolios/{portfolio_id}/realised-pnl

These endpoints expose only the metric defined by Decision F005:

GROSS_TRADE_CASH_REALISED_PNL

The response therefore includes that metric identifier explicitly and must not be interpreted as net, fee-adjusted, tax-adjusted or FX-converted realised P&L.

### Exact monetary wire representation

Every exact monetary value exposed by these endpoints uses a canonical rational representation:

{
  "currency_code": "USD",
  "amount": {
    "numerator": "100",
    "denominator": "3"
  }
}

The numerator and denominator are JSON strings representing base-10 integers.

The wire representation is mathematical and does not depend on Python Fraction as a public implementation contract.

Canonical rational rules are:

denominator is strictly positive;
numerator and denominator are reduced to lowest terms;
the sign, if negative, appears only in numerator;
zero is represented as 0/1;
an integer N is represented as N/1.

No floating-point or approximate Decimal value is exposed.

The API does not expose rounded, formatted or display-oriented monetary amounts.

Presentation rounding is deferred to a separate future policy.

### Resolved P&L

Resolved component detail is not exposed in the first public read contract.

Instead, the response exposes exact resolved gross trade-cash realised P&L aggregated by currency:

resolved_pnl_by_currency

Each currency appears at most once and uses the canonical exact-money representation.

Currencies are ordered by currency_code ascending.

If resolved components exist in a currency and their exact subtotal is zero, that currency remains present as an exact 0/1 result.

Currencies are never combined through implicit FX conversion.

### Unresolved components

Unresolved financial state remains explicit and is never represented as zero realised P&L.

Public unresolved components form a discriminated union identified by:

reason

Supported F005 reasons are:

CURRENCY_MISMATCH
MISSING_ACQUISITION_BASIS

Every unresolved component contains enough source context to explain the incomplete result:

account_id
sell_transaction_id
instrument_id
instrument_name
effective_date
quantity
allocated_proceeds
reason

quantity remains an exact decimal string using the existing API quantity representation.

A CURRENCY_MISMATCH component additionally contains:

removed_basis

as exact money.

It does not contain numeric realised P&L because subtraction across currencies is undefined without an FX methodology.

A MISSING_ACQUISITION_BASIS component does not contain removed_basis or numeric realised P&L.

Missing financial values are therefore represented structurally by the discriminated result shape rather than by ambiguous nullable monetary fields.

### Identity and metadata

account_id, sell_transaction_id and instrument_id are canonical source identifiers.

instrument_name is display metadata and is not used as financial identity.

The API does not expose source BUY transaction IDs in this summary contract.

A future disposal-detail capability may expose deeper lot/match provenance if product requirements justify it.

### Account response

GET /accounts/{account_id}/realised-pnl returns conceptually:

metric
resolved_pnl_by_currency
unresolved_components
is_fully_resolved

is_fully_resolved is true exactly when the result contains no unresolved components.

A valid Account with no realised SELL activity returns HTTP 200 with empty resolved and unresolved collections and is_fully_resolved = true.

### Portfolio response

GET /portfolios/{portfolio_id}/realised-pnl uses the same top-level contract.

Portfolio resolved P&L is aggregated only after independent Account-level F004/F005 reconstruction and only within the same currency.

Unresolved components retain their account_id so Account-boundary provenance is never lost during Portfolio aggregation.

The Portfolio endpoint does not expose a synthetic cross-currency total.

### Ordering

Public output is deterministic.

Resolved currency subtotals are ordered by currency_code ascending.

Unresolved components are ordered primarily by SELL effective date and SELL transaction identity, while multiple components of the same SELL preserve deterministic reconstruction order.

Ordering is presentation behavior and does not alter F004/F005 financial semantics.

### Error and unresolved semantics

A missing Account or Portfolio uses the existing HTTP 404 behavior.

A valid financial result containing unresolved F005 components remains HTTP 200.

CURRENCY_MISMATCH and MISSING_ACQUISITION_BASIS are valid financial states, not transport or validation errors.

Malformed canonical history or violated F004/F005 reconstruction invariants remain internal failures and are not reported as HTTP 422 errors for the read request.

### Application orchestration

The API layer does not perform financial reconstruction or rational arithmetic.

Account reads reuse the existing one-history-load reconstruction path:

canonical Account history
→ LotTransactionFact mapping
→ F004 FIFO
→ F005 reconstruction
→ Account summary
→ API mapping

Portfolio reads continue to reconstruct each Account independently before Portfolio aggregation.

The API must not reload or recompute F004/F005 merely to produce its wire representation.

Instrument metadata is loaded in a bounded operation and mapped by canonical instrument_id; per-component database lookups are not introduced.

### Persistence

Realised P&L remains computed derived state.

Decision 015 introduces:

no P&L table
no materialized view
no API snapshot
no cache
no database migration

Canonical transaction history remains the persisted source of truth.

### Testing

The public API must be tested for:

empty results;
exact profit;
exact loss;
exact zero;
repeating rational values;
multiple currencies;
currency mismatch;
missing acquisition basis;
partially resolved results;
Account isolation;
Portfolio aggregation;
missing resources;
canonical rational JSON representation;
absence of monetary rounding.

Existing F003, F004 and F005 financial-engine, golden/reference and PostgreSQL tests must remain green.

**Reason**

The existing F005 implementation produces exact and financially honest internal results but does not yet provide an externally usable product capability.

A public read contract must preserve exact rational monetary values and explicit unresolved financial states without inventing presentation rounding or FX methodology.

Representing money as a canonical numerator/denominator rational plus currency is lossless, language-independent and does not require clients to accept binary floating-point or finite Decimal approximations.

Publishing only resolved currency summaries plus unresolved component detail provides the minimum useful product contract without exposing every internal FIFO or realised-match structure.

**Consequences**

API clients can retrieve exact Account and Portfolio gross trade-cash realised P&L.

Clients must support arbitrary-size rational monetary values rather than assuming JSON numeric money.

Resolved P&L remains partitioned by currency.

Unresolved missing-basis and currency-mismatch states remain visible and cannot be mistaken for zero P&L.

The API intentionally provides no display rounding and no cross-currency Portfolio total.

Detailed resolved disposal/match audit APIs remain deferred.

The milestone remains fully computed on read and introduces no persistence or migration changes.

## Decision 016 — MVP v0.1 re-baseline

**Decision**

The first usable MVP is a single-user personal manual investment journal. Its immediate scope is defined in `PRODUCT.md` and must expose supported journal workflows through the web, not only API clients.

The approved F001–F005 financial foundation and current modular-monolith architecture are retained, including canonical history, independent quantity/price/cash facts, exact arithmetic, Account isolation, explicit unresolved states, no implicit FX and lossless rational public money. Derived financial state remains computed from canonical history; new caches, snapshots or materialized state require a concrete need.

Productisation now has priority over adding another financial engine. Corrections of supported manual journal events are required before regular journal use. Operational backup/restore is required before regular real-data use, and an appropriate access-control boundary before untrusted/public deployment.

Valuation, performance and benchmark comparison remain future product capabilities, not blockers for the first usable v0.1. This explicitly updates the original broad MVP and the immediate-release interpretation of Decision 002; performance/benchmark remain part of the long-term core value.

Milestones are defined by user-visible product capability rather than internal foundation completion. The next product milestone is Manual Portfolio Workspace: “Investment Tracker can now let its owner record trades and inspect holdings and realised results in the browser.”

Specialised Finance/Architecture decisions are required only when their durable financial-semantic or architectural-boundary domain changes. Ordinary implementation details remain Development's responsibility under the Process v2 guidance in `AGENTS.md`.

**Reason**

The existing backend can already reconstruct supported quantities and gross realised results correctly, but those capabilities are not yet available through a usable browser workflow. A narrower release converts this foundation into user value without redesigning it.

**Consequences**

`PRODUCT.md` separates MVP v0.1, SOON AFTER and LATER; README describes actual implemented status rather than the complete target. Decisions 001–015 remain historical records, and F001–F005 methodology is unchanged. Process v2 uses one final complete-capability review by default and one coherent PR per meaningful capability, with focused re-review only for actual blockers.

## Decision 017 — Manual transaction corrections API

**Decision**

F006 corrections use `PUT /accounts/{account_id}/transactions/{transaction_id}` and `DELETE` on the same resource. Only persisted DEPOSIT / BUY / SELL types are supported; unsupported types use the existing invalid-input convention (422).

PUT represents complete corrected factual state, not PATCH. DEPOSIT requires effective_date, currency_code and cash_amount. BUY/SELL requires instrument_id, effective_date, currency_code, quantity, price, cash_amount and settlement_date; settlement_date is required but nullable, with null clearing it. Type is determined by the existing persisted transaction, not the request. Extra fields are rejected; note and canonical relations are not editable.

Update mutates the existing row in place and preserves ID, type, Account, created_at, related_transaction_id and note. Existing create domain validation is reused, including exact representability and independent quantity/price/cash semantics. Success is 200 with the existing TransactionRead representation, not derived results.

DELETE hard-deletes the canonical row and returns 204 without a body. Account ownership is enforced for both operations. A transaction belonging to another Account is indistinguishable from a missing transaction (404). Existing restrictive inbound canonical related_transaction_id FK blocks deletion through the existing persistence-conflict / HTTP 409 behavior. No cascade, automatic detachment or nulling is allowed. Derived dependencies do not block mutations.

Each mutation loads, checks ownership/type, validates, mutates/deletes and commits atomically through the existing UoW. Failure rolls back. Repositories do not independently commit. Financial engines are not invoked during mutation: current history is reconstructed on read. The browser refetches History, Holdings and Realised result after success; Portfolio reads must not retain stale results.

Concurrency is last-write-wins. No ETag, If-Match, optimistic locking or version column is introduced. Existing Account history read is sufficient for edit prefill; no transaction-details endpoint is added.

**Reason**

An Account-scoped full correction contract provides browser journal correction without changing financial methodology or canonical identity, which is also the FIFO tie-break key.

**Consequences**

No migration, soft delete, audit/versioning, revision table, reversal model, generic CRUD framework, derived cache or financial-engine change is introduced. Corrected facts immediately become the source for existing deterministic derived reads. Concurrent stale-tab writes are an accepted v0.1 limitation.

## Decision 018 — Cash, income and outflow capability

**Decision**

Implement F007/F008 as one complete Account-centric browser capability, extending the existing manual journal and correction boundaries without redesigning them. Decisions 001–017 remain historical approved records; Decision 018 extends Decision 017's original correction scope to all eight canonical types and permits Instrument/relation corrections for Fee/Tax.

Use separate strong domain constructors and application create use cases for WITHDRAWAL, DIVIDEND, COUPON, FEE and TAX. Add Account-scoped POST /withdrawals, /dividends, /coupons, /fees and /taxes (201 TransactionRead). Withdrawal accepts cash/currency/date and optional note; income also requires Instrument; charges permit nullable optional Instrument/relation. Reject extra fields and trade-only quantity/price/settlement. Do not introduce a generic transaction-create API.

Existing PUT/DELETE /accounts/{account_id}/transactions/{transaction_id} support all eight persisted types. PUT is complete factual replacement with type-specific shapes, not PATCH: cash-flow date/currency/cash; income adds required Instrument; Fee/Tax adds required-but-nullable Instrument and related_transaction_id; trades retain existing full shape including required nullable settlement_date. Extra fields, omitted required fields and mismatched persisted-type shapes are invalid. Keep identity, Account, type, created_at and note; explicitly update UTC updated_at only on success. Fee/Tax nulls explicitly clear links. Existing inbound restrictive FK surfaces 409, without a new conflict model.

Mutation application logic validates Account, Instrument if provided, relation if provided, and the appropriate domain constructor, then persists and commits once through the existing UoW. Wrong-Account relations use the same 404 as missing parents. Invalid charge parents/self-relations/Instrument mismatch use 422. Repositories perform no independent commit. No financial engines are invoked during mutations.

Add GET /accounts/{account_id}/money-summary and GET /portfolios/{portfolio_id}/money-summary with required as_of_date=YYYY-MM-DD. There is no implicit server-today or from/to window. Existing resources without included activity return 200 with empty currencies; missing resources return 404. Malformed history is an internal failure, not request 422. Load canonical history once per Account and call pure F008 reconstruction. Portfolio reads reconstruct each Account before same-currency aggregation. Return {as_of_date, currencies}, with all monetary fields exact normalized decimal strings and sorted currency codes. Keep existing F005 rational API unchanged.

The browser extends existing Record/Edit/Delete dialogs and History, not a parallel CRUD subsystem. Record type selection groups Cash, Trades, Income and Charges. Income uses Gross amount plus visible gross/withholding/net-only guidance. Fee/Tax have explicit optional Instrument (None — account-level), optional relation (None — standalone), and a searchable native keyboard-accessible picker from loaded Account History excluding Fee/Tax parents. Labels include type/date/Instrument/cash/currency/identity. Never silently change Instrument when selecting a parent; explicit non-null mismatch is inline invalid. Relations visibly explain context-only semantics.

Account tabs are Holdings, History, Money and Realised result; Portfolio tabs are Holdings, Money and Realised result. Money groups per-currency recorded cash balance, external flows, trading cash, gross investment income/dividend/coupon, and separate Fee/Tax totals. No cross-currency, net-income or combined-expense total. A labelled native as-of date starts at browser-local today, fetches only Money immediately on a valid change, persists across tabs within the same context and resets on Account/Portfolio context change. It has no Apply button, date range or persisted storage. Future cutoffs are valid. Render exact strings with grouped integer digits, Unicode minus and currency, never Number, parseFloat or approximation. Retain loading/empty/error/stale guards, active zero and normal negative balances. Malformed monetary payloads fail safely.

History uses readable labels and type-specific details without irrelevant nullable columns; all eight types expose Edit/Delete. Successful mutations refresh History, Holdings, Money and Realised result; Portfolio summary is fetched fresh on entry. Preserve duplicate-submit locks, abort/unmount and stale-context guards. Provide understandable relation-conflict deletion guidance with explicit assurance that nothing was removed. Narrow layouts retain stacked dialogs/cards, horizontally scrollable tabs and readable per-currency Money sections.

**Reason**

The existing canonical model already represents all eight monetary events and optional relations. Separate factual entry, exact read reconstruction and current-history correction make income/outflows usable without prematurely adding net-return, fee allocation, FX or settlement semantics.

**Consequences**

No schema migration is required or introduced. No financial snapshots/caches, new tables/flags, generic transaction framework, relation-candidate endpoint, audit/revision model, dependencies, authentication redesign, valuation/performance, imports or integrations are added. Existing F001–F006 and F003–F005 golden regressions remain substantively unchanged. Tests cover strong event validation, atomic relation/correction behavior, exact scale-eight reconstruction and wire output, Account-first Portfolio reads, unchanged F005 gross results, browser lifecycle/date behavior and complete desktop/narrow journeys.

## Decision 019 — Local and cloud runtime

**Decision**

Local development uses Docker Compose with Web (Next.js, Node 24/pnpm), API (FastAPI, Python 3.14/uv) and PostgreSQL. Preserve the existing persistent PostgreSQL volume and loopback host mapping `127.0.0.1:55432:5432`. Web and API expose local ports 3000 and 8000 and support source hot reload. Inside Compose, API connects to `db:5432`; Web uses server-side `API_URL=http://api:8000`. Keep browser → same-origin `/api/*` → Next.js rewrite → FastAPI.

Local API startup waits for healthy PostgreSQL and successfully applies `alembic upgrade head` before starting Uvicorn. Migration failure prevents startup. Normal browser development uses `investment_tracker`; backend tests and E2E use only the separate disposable `investment_tracker_test`, preserving existing test safeguards. Normal `docker compose down` retains data; volume removal is an explicit destructive action.

The approved cloud topology is one Vercel Project with two Services: Web rooted at `apps/web` and API at `apps/api`, preserving Node 24 and Python 3.14. Web → API uses a Vercel Service Binding exposed as server-side `API_URL`, not manually constructed Preview API URLs. Preview connects only to an isolated staging Supabase PostgreSQL project; Production connects only to a separate production Supabase PostgreSQL project. Preview must never receive production database credentials. Supabase is PostgreSQL only, not browser persistence, Data API, Auth or Edge Functions.

`DATABASE_URL` is the application runtime connection. Local runtime retains ordinary SQLAlchemy pooling. Cloud runtime uses Supabase transaction pooling with SQLAlchemy NullPool, prepared statements disabled where required and TLS preserved. `MIGRATION_DATABASE_URL` is the operator/Alembic direct connection, with local/CI fallback to the existing runtime URL when absent; `TEST_DATABASE_URL` remains disposable local/CI configuration. `DATABASE_POOL_MODE` distinguishes local and serverless policies when that support is implemented and verified. Cloud migrations are explicit operator operations, never API startup or request work. Alembic remains schema authority; production migration requires a backup first.

Use approved Vercel deployment protection for all deployments where available; real financial data must not be publicly readable/writable. No custom application authentication is introduced here. Before real-data readiness, establish a project-controlled direct-connection logical backup procedure and verify a synthetic restore into disposable non-production PostgreSQL. Never restore destructively into Production.

**Reason**

A one-command local runtime makes the existing journal reproducible while the approved cloud topology retains the same browser/API boundary. Separate staging/production databases, explicit migrations and operational safety gates prevent Preview work from affecting real financial data.

**Consequences**

No financial methodology, API contract, schema or product UX changes are required. Preserve Decisions 001–018 and F001–F008 substantively. Local Docker may be delivered independently; approved cloud architecture is not a claim of cloud implementation. Factual implementation/readiness lives in OPERATIONS and README.

Stop before substituting another topology if Vercel Services/account behavior blocks the approved design. Stop before purchase/upgrade if two isolated Supabase projects cannot be provisioned under the approved account limits. Never alter unrelated resources to release capacity. If deployment protection requires an unapproved paid change, production real-data readiness is blocked. No cloud readiness may be claimed without environment isolation, access protection, direct-endpoint connectivity and the backup/restore gate being verified.
