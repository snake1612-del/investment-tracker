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
