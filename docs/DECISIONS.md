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
