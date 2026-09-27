# Financial calculations and accounting semantics

This file is the source of truth for approved financial calculation and accounting semantics in Investment Tracker.

Implementation must follow the methodology documented here.

Codex must not invent missing financial methodology, infer unresolved accounting rules from database structure, or silently choose one financial convention where the project has not approved one.

Unresolved methodology remains explicitly deferred until a corresponding financial decision is accepted and recorded here.

# Decision F001 — Canonical transaction semantics

## Sign convention

Canonical transaction values use unsigned/non-negative magnitudes.

Direction is determined only by transaction `type`:

```text
DEPOSIT    → +cash
WITHDRAWAL → -cash
BUY        → +position / -cash
SELL       → -position / +cash
DIVIDEND   → +cash
COUPON     → +cash
FEE        → -cash
TAX        → -cash
```

Do not persist signed quantity or signed cash as the canonical convention.

For example:

```text
DEPOSIT 100000
```

means a cash increase of 100000.

```text
WITHDRAWAL 10000
```

means a cash decrease of 10000.

The sign is derived from the transaction type rather than stored in the canonical numeric magnitude.

## BUY / SELL factual inputs

For BUY and SELL, the canonical model may store independently:

- `quantity`;
- `price`;
- `cash_amount`.

When the source provides all three, all three may be persisted as factual inputs.

Do not silently force:

```text
cash_amount = quantity × price
```

The multiplication may be used as a reconciliation or validation calculation.

It must not automatically rewrite canonical source facts.

## Fees

`FEE` is a separate canonical transaction.

Example:

```text
BUY
+
FEE related to BUY
```

A FEE may also be standalone.

Several FEE transactions may relate to one originating transaction.

A fee must not be embedded into BUY/SELL canonical facts merely because it belongs to the same economic event when it can be represented as its own factual transaction.

The methodology for whether and how fees affect cost basis remains a separate unresolved financial decision.

## Taxes

`TAX` is a separate canonical transaction.

TAX represents actual tax paid or withheld.

It does NOT represent:

- estimated tax;
- future tax liability;
- tax forecast.

A TAX transaction may be linked to an originating transaction or may be standalone.

Calculated tax liability remains a separate unresolved methodology.

## Dividend / Coupon

When gross income and withholding are both known:

- `DIVIDEND` or `COUPON` stores gross income;
- withholding is stored as a separate `TAX` transaction.

Example:

```text
DIVIDEND 100
TAX 13
```

Derived net cash:

```text
87
```

Do not store net income together with a separate TAX transaction if that would double-count withholding.

Handling incomplete source data where only net income is known remains explicitly deferred.

## cash_amount

`cash_amount` is:

> the non-negative magnitude of the monetary leg represented by that canonical Transaction, in that Transaction's currency, before separately represented linked FEE/TAX transactions.

It is not necessarily the net amount of the entire economic event.

For example, if a BUY and its commission are represented as separate BUY and FEE transactions, the BUY `cash_amount` does not include rewriting the separate FEE into the BUY monetary leg.

## Currency

Each canonical Transaction has one monetary currency.

Linked transactions may use different currencies.

Example:

```text
BUY 1000 USD
FEE 180 RUB
```

Do not add `fee_currency` or `tax_currency` fields inside BUY merely to represent linked charges in another currency.

Each FEE or TAX transaction carries its own transaction currency.

The broader FX event/rate/P&L methodology remains deferred.

## Dates

`effective_date` represents the business-effective date of the canonical event.

For BUY/SELL:

```text
effective_date = trade/execution date
```

For other transaction types, it is the business-effective date of that event.

`settlement_date` is optional and primarily represents an actual known settlement date where settlement is relevant.

Never hardcode or infer T+1/T+2 as canonical fact when the actual settlement date is not known.

## Corrections

Manual-entry v1 is not an immutable ledger.

Canonical transactions may be explicitly edited or deleted through application logic.

Any derived state must remain recomputable from the resulting canonical transaction history.

Mandatory reversal transactions, append-only ledger behavior and full audit semantics are deferred.

## Deferred financial methodology

The following areas are explicitly unresolved and must not be invented during implementation:

- fee → cost basis treatment;
- FIFO/lots;
- realised P&L;
- unrealised P&L;
- accrued interest / bond clean-vs-dirty price;
- incomplete/net-only dividend imports;
- FX settlement event model;
- FX rates and FX P&L;
- broker cancellation/correction provenance;
- calculated tax liability;
- corporate actions.

When implementation requires one of these rules, methodology must be approved first and recorded in this document before the financial behavior is implemented.
