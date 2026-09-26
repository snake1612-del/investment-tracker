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
