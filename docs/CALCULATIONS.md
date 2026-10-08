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

# Decision F002 — Manual BUY / SELL canonical entry semantics

## Scope

Decision F002 определяет financial/accounting semantics для ручного ввода canonical BUY и SELL transactions в первой версии Investment Tracker.

Он не изменяет canonical transaction model Decision F001.

Canonical persistence остаётся способна представлять более широкий набор source data, тогда как manual BUY/SELL v1 использует более строгую application/domain validation.

## Required and optional fields

Для manual BUY и SELL обязательны:

- `instrument_id`;
- `quantity`;
- `price`;
- `cash_amount`;
- `currency_code`;
- `effective_date`.

Optional:

- `settlement_date`;
- `note`.

Manual entry требует одновременного наличия `quantity`, `price` и `cash_amount`, даже несмотря на то, что canonical persistence model допускает nullable `quantity` и `price` для поддержки других transaction types и будущих import scenarios.

## Canonical direction and magnitudes

BUY и SELL используют unsigned/non-negative canonical magnitudes согласно Decision F001.

Для manual BUY/SELL:

- `quantity > 0`;
- `price > 0`;
- `cash_amount > 0`.

Direction определяется только transaction `type`:

```text
BUY  → +position / -cash
SELL → -position / +cash
```

Signed `quantity`, `price` или `cash_amount` не используются для кодирования direction.

## Trade cash_amount

Для BUY/SELL:

`cash_amount` — factual monetary leg самого trade в currency этой Transaction.

Он не включает отдельно представленные:

- FEE;
- TAX.

Если комиссия или налог представлены отдельными canonical transactions, их amounts не должны встраиваться обратно в BUY/SELL `cash_amount`.

`cash_amount` не обязательно равен экономическому net cash всей группы связанных transactions.

## Independent factual inputs and reconciliation

Для manual BUY/SELL:

- `quantity`;
- `price`;
- `cash_amount`;

являются независимыми factual inputs.

Нельзя silently заменять введённый `cash_amount` значением:

```text
quantity × price
```

Если exact arithmetic показывает:

```text
quantity × price != cash_amount
```

trade остаётся valid canonical entry.

Application может и желательно должна показывать non-blocking reconciliation warning, если такое расхождение обнаружено.

Однако warning:

- не блокирует сохранение;
- не изменяет введённые factual values;
- не вводит tolerance;
- не вводит financial rounding methodology.

Decision F002 не определяет допустимую величину такого расхождения.

## Fees

FEE остаётся отдельной canonical Transaction согласно Decision F001.

Для одного BUY или SELL может существовать:

- zero FEE transactions;
- one FEE transaction;
- multiple FEE transactions.

FEE может ссылаться на originating trade через canonical transaction relationship.

FEE также может быть standalone там, где это соответствует фактическому source event.

Decision F002 не определяет fee → cost basis treatment.

Эта методология остаётся deferred.

## Taxes

TAX остаётся отдельной canonical Transaction.

TAX означает только фактически:

- paid tax;
- withheld tax.

SELL не требует наличия TAX.

Manual BUY/SELL workflow не рассчитывает tax автоматически.

Не создаются:

- estimated tax;
- future tax liability;
- tax forecast.

Связанный TAX может относиться к originating trade, но tax-basis methodology остаётся deferred.

## Currency semantics

Для BUY/SELL:

`currency_code` является currency factual trade `cash_amount`.

Для manual BUY/SELL `currency_code` MUST состоять ровно из трёх uppercase ASCII letters.

Conceptually:

```text
[A-Z]{3}
```

Decision F002 не вводит supported-currency whitelist.

Linked FEE/TAX transactions могут иметь другую currency.

Например:

```text
BUY cash_amount: 1000 USD
FEE cash_amount: 180 RUB
```

Из различия currencies не выводится никакая FX conversion.

Decision F002 не определяет:

- FX event model;
- exchange rate;
- FX conversion;
- FX P&L.

## Price semantics

Для manual BUY/SELL v1:

`price` — direct monetary unit price, выраженная в той же currency, что и trade `cash_amount`.

Эта semantics применяется только к instruments, которые корректно представляются через direct monetary unit price.

Decision F002 НЕ определяет:

- bond percentage quotation;
- clean price;
- dirty price;
- accrued interest;
- nominal/par quotation rules;
- instrument-specific quotation conventions.

Canonical schema сейчас не расширяется полями вроде:

- `price_currency`;
- `quotation_type`;
- отдельной quotation model.

Instrument-specific price semantics должны быть утверждены отдельно до реализации инструментов, для которых direct monetary unit price недостаточна.

## SELL and reconstructed position

Manual SELL не должен отклоняться только потому, что:

```text
sell quantity > currently reconstructed position
```

Current position является derived state.

Он может быть:

- incomplete;
- reconstructed from incomplete history;
- temporarily incorrect из-за out-of-order historical entry.

Поэтому reconstructed position не является blocking canonical-entry constraint для SELL.

Application может позднее показывать non-blocking oversell warning.

Это правило НЕ утверждает:

- short-selling methodology;
- negative-position accounting;
- margin rules;
- borrow accounting.

Такие semantics остаются unresolved.

## Dates

Для BUY/SELL:

`effective_date` является factual trade/execution date.

Historical/backdated manual entry разрешён.

`settlement_date`:

- optional;
- хранит factual actual settlement date, если она известна;
- остаётся NULL, если settlement date неизвестна.

Нельзя автоматически выводить:

- T+1;
- T+2;
- другую settlement convention.

Для manual BUY/SELL применяется application/domain rule:

```text
if settlement_date is present:
    settlement_date >= effective_date
```

Это правило относится к manual-entry v1.

Decision F002 не требует превращать его в universal database constraint для всех будущих imports или source formats.

## Corrections

Manual-entry v1 остаётся editable canonical history согласно Decision F001.

Explicit edit/delete canonical transactions разрешены через application logic.

Decision F002 не вводит:

- mandatory reversal transactions;
- append-only ledger;
- immutable accounting journal;
- complete audit trail model.

Эти semantics остаются deferred.

## Exact Decimal and storage precision

Canonical BUY/SELL values используют exact decimal representation.

Persistence precision остаётся:

```text
quantity    → NUMERIC(28,12)
price       → NUMERIC(28,12)
cash_amount → NUMERIC(24,8)
```

Python representation:

```text
Decimal
```

Manual factual values должны быть exactly representable в соответствующей canonical storage precision.

Значение, которое невозможно представить без изменения factual value, должно быть rejected.

Нельзя silently:

- round;
- truncate;
- convert through binary floating point.

Storage precision сама по себе НЕ определяет:

- financial rounding rules;
- tick size;
- allowed instrument precision;
- currency rounding;
- exchange-specific quotation increments.

Такие правила должны утверждаться отдельно при необходимости.

## Deferred financial methodology

Decision F002 намеренно не определяет:

- FIFO;
- lots;
- average cost;
- realised P&L;
- unrealised P&L;
- fee → cost basis treatment;
- tax basis;
- corporate actions;
- bond accounting;
- bond quotation conventions;
- clean/dirty price;
- accrued interest;
- amortization;
- redemption;
- FX;
- valuation;
- market data;
- TWR;
- XIRR;
- benchmarks;
- import normalization;
- orders/executions/partial fills;
- settlement accounting engine;
- short-selling methodology.

Implementation must not invent answers for these areas.

Если дальнейшая implementation требует любой из этих semantics, соответствующая financial methodology должна быть утверждена до реализации.

## Reason

Canonical persistence model должна быть достаточно гибкой для разных transaction types и будущих source formats, поэтому Decision 008 допускает nullable `quantity` и `price`.

Manual BUY/SELL entry имеет более узкий и контролируемый context.

Для него одновременно известные:

- instrument;
- quantity;
- unit price;
- factual cash leg;
- currency;
- execution date;

дают достаточно информации, чтобы сохранить trade как canonical fact без вычисления или переписывания одного факта из другого.

Отделение reconciliation от canonical entry позволяет сохранить фактические broker/manual values даже тогда, когда `quantity × price` не совпадает с `cash_amount` из-за ещё не моделируемых quotation, source или accounting особенностей.

Отдельные FEE/TAX transactions сохраняют canonical event decomposition Decision F001 и не заставляют BUY/SELL принимать premature cost-basis или tax semantics.

## Consequences

Manual BUY/SELL validation становится строже, чем physical canonical persistence schema.

Manual trade нельзя создать без:

- instrument;
- positive quantity;
- positive direct unit price;
- positive factual cash amount;
- structurally valid currency code;
- execution date.

При этом `quantity`, `price` и `cash_amount` остаются независимыми canonical facts.

Reconciliation mismatch не блокирует canonical entry и не переписывает source values.

FEE и TAX остаются отдельными transactions.

SELL не зависит от reconstructed position как blocking validation rule.

Decimal values, которые невозможно точно представить в утверждённой persistence precision, отклоняются вместо silent rounding.

Decision F002 не расширяет persistence schema и не вводит instrument quotation, FX, cost basis, P&L, tax или settlement-accounting methodology.

# Decision F003 — Position quantity reconstruction

## Scope and source of truth

An Account position quantity is derived from canonical Transaction history for one Account and one Instrument. It is recomputable, not an independent persisted accounting fact.

For an explicit `as_of_date`, include only transactions whose `effective_date <= as_of_date`:

```text
position quantity = Σ BUY.quantity − Σ SELL.quantity
```

The quantity effect of every current canonical transaction type is:

```text
BUY        → +quantity
SELL       → -quantity
DEPOSIT    → 0
WITHDRAWAL → 0
DIVIDEND   → 0
COUPON     → 0
FEE        → 0
TAX        → 0
```

Future transaction types require an explicit quantity-effect decision; they must not silently default to zero.

`instrument_id` is the identity used for grouping. Instruments with the same name remain separate when their IDs differ.

## Dates and ordering

`effective_date` determines whether a transaction is included. Backdated transactions change the result for applicable evaluation dates regardless of when they were inserted.

`settlement_date`, transaction ID, insertion order and the order of transactions on the same date do not determine quantity. No settled/unsettled position subsystem is introduced.

## Exact arithmetic and malformed facts

BUY and SELL require both `instrument_id` and `quantity` for reconstruction. Their absence is malformed canonical history and must fail explicitly, without skipping, treating the event as zero, or repairing it.

Canonical quantity is converted exactly to integer units of `10^-12`; signed units are aggregated with arbitrary-precision integers and converted back to `Decimal` exactly. Neither conversion nor aggregation may depend on the ambient Decimal context, round, truncate, or quantize-to-fit. A quantity not exactly representable at scale 12 fails explicitly.

A derived sum may have more significant digits than one `NUMERIC(28,12)` input. It is not persisted in that column.

`price`, `cash_amount`, currency and FEE/TAX amounts do not affect position quantity.

## Zero and negative results

Zero is a valid financial result. A negative result is preserved without clamping, rejection, or warning. This decision does not establish short-selling accounting or classification.

Reconstruction does not automatically correct incomplete or corrupt canonical history.

## Deferred methodology

This decision defines quantity only. It does not define lots, FIFO/LIFO, average cost or price, cost basis, realised or unrealised P&L, valuation, allocation, FX, performance, settlement accounting, corporate actions, or short-selling methodology.

# Decision F004 — FIFO lot and long-position cost-basis reconstruction

## Decision

Canonical transaction history remains the financial source of truth.

Acquisition lots and cost basis are recomputable derived state.

Each canonical BUY creates one distinct acquisition lot within its `(InvestmentAccount, Instrument)` stream.

An acquisition lot derives:

- its source BUY transaction identity;
- acquisition date from `BUY.effective_date`;
- original quantity from `BUY.quantity`;
- original acquisition basis from `BUY.cash_amount`;
- basis currency from `BUY.currency_code`;
- remaining quantity;
- remaining acquisition basis.

BUY lots are not automatically merged.

Lot reconstruction and SELL matching occur independently within each `(account_id, instrument_id)` pair.

A SELL in one InvestmentAccount MUST NOT consume a BUY lot from another InvestmentAccount.

FIFO reconstruction processes BUY and SELL transactions in one deterministic order:

1. `effective_date ASC`;
2. `transaction_id ASC`.

When a BUY is encountered, it creates an acquisition lot.

When a SELL is encountered, its quantity consumes currently available open BUY lots in FIFO order under that same chronology.

`transaction_id` is a deterministic same-date tie-break for v1. It does not claim to represent actual intraday execution chronology.

Backdated transaction insertion, transaction edits and transaction deletion require complete deterministic recomputation from the current canonical history. Existing derived FIFO assignments are not immutable.

For F004, the authoritative original acquisition basis of a BUY lot is `BUY.cash_amount`.

`BUY.price` remains a canonical factual unit-price value but does not determine total acquisition basis.

The system MUST NOT replace BUY cash amount with `quantity × price`.

F004 cost basis excludes FEE and TAX.

Linked FEE transactions do not increase BUY acquisition basis and do not otherwise modify lot basis in this decision.

TAX does not affect acquisition lot basis.

Fee-adjusted basis and tax basis are deferred to later financial methodology.

When a SELL consumes quantity `q` from a lot with original quantity `Q` and original acquisition basis `B`, the acquisition basis removed by that match is mathematically:

`B × q / Q`.

Proportional acquisition-basis allocation MUST remain mathematically exact.

If division produces a repeating decimal, reconstruction MUST preserve the exact rational result rather than silently rounding to currency minor units, canonical cash precision or another decimal scale.

No binary floating-point arithmetic or silent monetary rounding is permitted.

For each acquisition lot, the following invariants hold exactly:

`original quantity = cumulative disposed quantity + remaining quantity`

and:

`original acquisition basis = cumulative removed acquisition basis + remaining acquisition basis`.

If a lot is fully disposed, its remaining quantity and remaining basis are zero and its cumulative removed acquisition basis equals its original acquisition basis exactly.

SELL quantity determines lot consumption.

SELL price and SELL cash amount do not determine acquisition basis removed from a matched lot. SELL monetary facts are reserved for future proceeds and realised-P&L methodology.

Each lot keeps the currency of its source BUY transaction.

FIFO quantity matching may operate across BUY lots with different basis currencies for the same Account and Instrument.

Monetary basis amounts in different currencies MUST NOT be added into one synthetic amount without FX methodology.

Instead, removed and remaining basis are preserved and aggregated by currency.

SELL currency does not affect FIFO quantity matching or the acquisition basis removed from BUY lots.

If a SELL quantity exceeds the quantity available in preceding supported long BUY lots, all available long lots are consumed under FIFO and the excess remains explicit unmatched SELL quantity.

The reconstruction engine MUST NOT:

- invent an implicit BUY;
- assign zero acquisition basis to the unresolved quantity as though it were known;
- clamp the excess away;
- match the SELL against a future BUY;
- invent short-position acquisition basis.

Unmatched SELL quantity indicates that long-position acquisition basis cannot be fully reconstructed from the available supported canonical history.

Matched long-lot results remain valid even when unmatched SELL quantity exists.

A future BUY does not retroactively resolve an earlier unmatched SELL under F004. Short-sale and short-cover cost-basis methodology are outside this decision.

A fully closed supported long position has:

- remaining open long quantity of zero;
- remaining open acquisition basis of zero.

Historical lots and disposal matches may still exist as derived history.

Portfolio-level cost basis is derived only after Account-level FIFO reconstruction.

There is no cross-account FIFO matching.

For the same canonical Instrument, Portfolio remaining acquisition basis may be summed across Accounts only within each basis currency. Mixed currencies remain separate.

Lot and matching identity use canonical `instrument_id`. Instrument names do not define identity.

Acquisition date is BUY `effective_date`.

Disposal date is SELL `effective_date`.

`settlement_date` does not participate in FIFO lot matching or F004 basis reconstruction.

F004 is valid for histories whose relevant long quantity evolution is represented by supported BUY and SELL canonical events.

Corporate actions, transfers with carried basis, stock splits, conversions, mergers, bond amortization and redemption require separate canonical semantics before their effects can be reconstructed.

No additional bond-specific pricing methodology is required for F004 because acquisition basis is derived from factual BUY cash amount rather than reconstructed from quoted price.

Average open cost per unit is not defined by F004.

Lots and cost basis remain recomputable derived state. F004 does not require persisted or materialized lot records.

## Reason

The project already treats canonical transaction history as the accounting source of truth and positions as derived state.

Canonical BUY transactions contain sufficient factual information to establish acquisition lots: Account, Instrument, quantity, cash amount, currency and effective date.

Using BUY cash amount as acquisition basis preserves the previously approved rule that quantity, price and cash amount are independent canonical facts and prevents the cost-basis engine from silently replacing broker/user-reported monetary facts with `quantity × price`.

FIFO provides a deterministic first lot-matching methodology, but unlike pure quantity reconstruction it requires a stable ordering for same-date transactions. `effective_date` followed by `transaction_id` provides a deterministic v1 order without inventing unavailable intraday chronology.

Exact proportional allocation is necessary because canonical quantities and cash amounts can produce non-terminating decimal ratios. Rounding each partial disposal would create order-dependent cumulative drift and could violate the invariant that full disposal removes exactly the original acquisition basis.

Preserving derived basis as an exact rational value until a future explicit rounding boundary avoids embedding presentation, currency or tax rounding rules in lot reconstruction.

Separating cost basis by currency permits factual multi-currency history to be reconstructed without introducing an FX engine.

Explicit unmatched SELL quantity allows the engine to preserve incomplete or oversold factual history without fabricating long acquisition basis or prematurely implementing short-selling accounting.

Deferring FEE treatment keeps F004 independent of unresolved fee eligibility, cross-currency fee conversion, tax rules and future realised-P&L methodology.

## Consequences

The backend financial domain may deterministically reconstruct long acquisition lots from canonical BUY/SELL history.

Each BUY creates one lot with:

- source BUY identity;
- original and remaining quantity;
- original and remaining acquisition basis;
- basis currency.

SELL transactions consume prior open BUY lots using FIFO within the same Account and Instrument.

FIFO chronology is determined by `effective_date ASC`, then `transaction_id ASC`.

Backdated inserts, edits and deletes require full recomputation.

BUY cash amount defines original acquisition basis.

BUY price does not calculate total lot basis.

FEE and TAX do not modify F004 basis.

Partial lot basis allocation uses exact proportional rational arithmetic with no intermediate financial rounding.

Full disposal removes exactly the lot's original acquisition basis.

SELL cash amount and SELL price do not alter acquisition basis allocation.

Mixed-currency acquisition lots remain valid and their basis is reported separately by currency.

Portfolio cost basis may aggregate Account-level results only per currency and only after separate Account-level FIFO reconstruction.

Oversold or incomplete history produces explicit unmatched SELL quantity. No implicit acquisition lot or short basis is invented.

Future BUYs do not retroactively match earlier unmatched SELLs.

Closed long lots have zero remaining quantity and zero remaining basis.

F004 does not define realised or unrealised P&L, fee-adjusted basis, tax basis, FX conversion, average-cost accounting, short-selling basis, corporate-action basis adjustments, bond redemption/amortization or persistence architecture.

# Decision F005 — Gross trade-cash realised P&L reconstruction

## Decision

Canonical transaction history remains the financial source of truth.

F004 FIFO DisposalMatches remain the authoritative derived long-lot assignment used for realised-P&L reconstruction.

Decision F005 defines gross trade-cash realised P&L.

The term "gross trade-cash" is intentional:

- canonical BUY and SELL cash legs are used directly;
- FEE is excluded;
- TAX is excluded;
- no FX conversion is performed.

For a canonical SELL, authoritative total realised proceeds are `SELL.cash_amount` in `SELL.currency_code`.

`SELL.quantity`, `SELL.price` and `SELL.cash_amount` remain independent factual values.

`SELL.cash_amount` MUST NOT be silently replaced by `SELL.quantity × SELL.price`.

`SELL.price` remains factual unit-price information but does not determine total realised proceeds and does not determine proceeds allocation between FIFO matches.

For a SELL with total quantity `Q` and cash amount `P`, proceeds attributable to a matched or unmatched quantity `q` are:

`P × q / Q`.

This allocation MUST be mathematically exact.

Every F004 DisposalMatch receives proceeds proportional to its matched quantity.

Any F004 unmatched SELL quantity receives a corresponding proportional factual proceeds component.

For every SELL:

`SELL.cash_amount = sum(match allocated proceeds) + unmatched allocated proceeds`

mathematically exactly.

If the SELL is fully matched:

`SELL.cash_amount = sum(all DisposalMatch allocated proceeds)`

exactly.

Proportional proceeds allocation MUST NOT silently round to currency minor units, canonical cash scale, Decimal context precision or any other presentation precision.

Binary floating-point arithmetic MUST NOT be used.

Derived proceeds allocation may therefore be an exact rational value.

For one DisposalMatch, gross trade-cash realised P&L is defined only when the allocated SELL proceeds currency equals the removed acquisition-basis currency.

When currencies are equal:

`gross trade-cash realised P&L = allocated SELL proceeds - removed acquisition basis`.

The result is an exact monetary amount in that currency.

Positive values are profits.

Negative values are losses.

Zero is a valid realised-P&L result.

Results MUST NOT be clamped.

When the allocated SELL proceeds currency differs from the removed acquisition-basis currency, numeric realised P&L for that DisposalMatch is unresolved.

The engine MUST preserve both monetary components and their currencies.

It MUST NOT subtract monetary amounts denominated in different currencies and MUST NOT invent an FX conversion.

Cross-currency unresolved state does not invalidate other resolved DisposalMatches.

A single SELL may therefore contain both resolved and unresolved realised-P&L components.

If F004 reports unmatched SELL quantity, F005 allocates factual SELL proceeds to that unmatched quantity proportionally.

The acquisition basis for unmatched quantity remains unresolved.

Gross realised P&L for unmatched quantity also remains unresolved.

The engine MUST NOT assign zero acquisition basis, fabricate an implicit BUY or invent short-position basis.

A SELL-only history therefore has factual SELL proceeds but unresolved acquisition basis and unresolved realised P&L.

F005 distinguishes at least two financially different unresolved conditions:

1. missing acquisition basis because SELL quantity is unmatched under supported long-lot history;
2. basis/proceeds currency mismatch requiring future FX methodology.

These conditions MUST NOT be treated as equivalent to zero P&L.

Resolved factual components remain usable even when another component of the same SELL is unresolved.

FEE does not affect F005 gross trade-cash realised P&L.

BUY-linked FEE does not modify the F004 acquisition basis used by F005.

SELL-linked FEE does not reduce F005 SELL proceeds.

Multiple, linked, unlinked or cross-currency FEE transactions remain separate canonical financial events.

Fee-adjusted and net realised-P&L methodology is deferred.

TAX does not affect F005 gross trade-cash realised P&L.

Tax basis, tax liability and tax-adjusted P&L remain deferred.

Realised-P&L reconstruction inherits the F004 Account and Instrument matching boundaries.

A SELL in one InvestmentAccount MUST NOT use acquisition basis from another InvestmentAccount.

Portfolio aggregation occurs only after Account-level reconstruction.

Resolved realised P&L may be summed only within the same currency.

Multi-currency results remain partitioned by currency.

A Portfolio or Account containing unresolved components may still expose its resolved P&L components, but those resolved values MUST NOT be represented as a complete total while unresolved components remain.

The realised event date is `SELL.effective_date`.

`settlement_date` does not determine F005 realised-P&L recognition.

Backdated BUY or SELL insertion, transaction edits and transaction deletion require deterministic recomputation from current canonical history and current F004 matching.

F005 does not create an immutable derived-P&L ledger.

Exact arithmetic applies throughout F005.

Canonical SELL cash amount is exact.

Proportional proceeds allocation is exact.

F004 removed acquisition basis remains exact.

Same-currency subtraction producing realised P&L is exact.

No binary float, silent monetary rounding or display rounding is part of the financial methodology.

F005 is valid only where F004 long-position FIFO matching is valid.

Corporate actions, transfers, mergers, conversions, redemption and amortization require separate future methodology.

No additional bond clean-price, dirty-price or accrued-interest methodology is required for F005 because realised proceeds and acquisition basis use factual canonical BUY/SELL cash legs.

Bond redemption and amortization remain deferred.

## Reason

Canonical SELL already contains the factual monetary proceeds required for realised-P&L reconstruction, while F004 provides deterministic FIFO assignment and exact removed acquisition basis.

Using `SELL.cash_amount` preserves the approved canonical rule that quantity, price and cash amount are independent facts and prevents F005 from replacing factual proceeds with `quantity × price`.

Proportional allocation by SELL quantity is necessary when one SELL spans multiple acquisition lots or includes unmatched quantity.

Exact rational allocation avoids cumulative rounding drift and ensures that allocated proceeds conserve the original canonical SELL cash amount exactly.

Calculating realised P&L at the DisposalMatch level preserves the economic relationship between a particular disposal and its removed acquisition basis and allows higher-level SELL, Account and Portfolio aggregation afterward.

A numeric P&L cannot be defined by directly subtracting amounts in different currencies. Preserving such matches as unresolved retains all known factual data without introducing an FX methodology.

Likewise, unmatched SELL quantity has known factual proceeds but unknown supported long acquisition basis. Preserving it as unresolved avoids fabricating zero basis or short-selling methodology.

Allowing partially resolved SELLs preserves useful same-currency P&L even when another component requires FX or has missing acquisition history.

Excluding FEE and TAX keeps F005 focused on gross trade-cash realised P&L and avoids prematurely coupling the milestone to fee allocation, FX, tax basis or net-P&L methodology.

## Consequences

The financial domain may reconstruct gross long-position trade-cash realised P&L from canonical SELL transactions and F004 FIFO DisposalMatches.

SELL cash amount is authoritative proceeds.

SELL price does not determine proceeds.

SELL proceeds are allocated exactly and proportionally by quantity across all matched and unmatched SELL components.

The total allocated proceeds of every SELL equal its canonical cash amount exactly.

Each same-currency DisposalMatch produces exact gross trade-cash realised P&L:

`allocated proceeds - removed acquisition basis`.

Cross-currency matches preserve allocated proceeds and acquisition basis but have unresolved numeric P&L until FX methodology exists.

Unmatched SELL components preserve factual proceeds but have unresolved acquisition basis and unresolved P&L.

A single SELL may be partially resolved.

Resolved values remain usable and aggregate by currency.

Unresolved components remain explicitly represented and are never treated as zero.

FEE and TAX do not affect F005 P&L.

Account boundaries remain strict.

Portfolio aggregation occurs after Account-level reconstruction and remains currency-partitioned.

Realised P&L is dated by SELL effective date.

Backdated canonical mutations trigger full deterministic recomputation.

F005 does not define unrealised P&L, valuation, FX conversion, fee-adjusted/net P&L, tax accounting, short-selling P&L, corporate actions, bond redemption/amortization or persistence architecture.

# Decision F006 — Manual Journal Corrections

## Decision

Manual DEPOSIT / BUY / SELL are mutable canonical facts. A correction changes the current best-known factual history through direct in-place edit, preserving the transaction ID. Deletion is canonical hard deletion: the event is absent from current history.

Correction is not a reversal, compensating economic event, revision record or soft deletion. A new actual economic event must be entered as a new transaction, not used to rewrite an earlier correct fact.

Effective date, Instrument and currency may be corrected. Transaction type and InvestmentAccount cannot be changed. An erroneous Account assignment is corrected by deleting the wrong record and creating the correct record under the correct Account.

Existing create validation applies without a second financial validator. Quantity, price and cash amount remain independent factual values; cash is never replaced with quantity × price.

All derived state reflects the current corrected canonical history under F003–F005. Derived dependencies never block correction or deletion, including deletion of an already-consumed BUY. Backdated corrections may change historical FIFO matching and realised P&L. They may create or remove MISSING_ACQUISITION_BASIS or CURRENCY_MISMATCH. Old derived outcomes are not preserved for stability.

An active canonical transaction related to a primary transaction blocks deletion of that primary transaction. Derived matches and positions are not canonical related transactions and do not constitute this deletion restriction.

## Reason

The manual journal must allow factual entry mistakes to be corrected before regular use, while keeping canonical identity and the F004 effective_date / transaction_id ordering stable.

## Consequences

The approved correction scope is DEPOSIT / BUY / SELL only. Existing identity, type, Account, note and canonical relations remain unchanged by an edit. There is no reversal model, audit trail or revision history. All existing reconstructions operate on current facts; F001–F005 remain unchanged.

# Decision F007 — Manual cash, income and outflow transaction semantics

## Decision

Manual entry and corrections now support all eight existing canonical types. This extends F006's original three-type scope without changing F001–F005 or introducing a new canonical model.

WITHDRAWAL is an external cash outflow. DIVIDEND and COUPON are gross investment income associated with a required Instrument. FEE and TAX are separate outflows, either account-level or associated with an optional Instrument. TAX represents actual paid or withheld tax only, never estimated liability, tax forecast or an automatically calculated tax.

Each new manual event requires a positive finite exact Decimal cash_amount, exactly representable as NUMERIC(24,8), a currency_code matching uppercase ASCII `[A-Z]{3}`, and a factual effective_date. Historical entry is allowed. Quantity, price and settlement_date are not inputs for these five types. Note is optional on create and remains unchanged by correction. WITHDRAWAL has no Instrument. No holdings or cash-sufficiency validation is imposed. A negative reconstructed cash balance is valid recorded state, not a mutation error.

DIVIDEND/COUPON cash_amount is the gross monetary leg before separately recorded withholding. When gross income and withholding are known, record gross income and a separate TAX. Net-only source data cannot yet be entered accurately; do not infer gross income, assume zero withholding, or record net income plus a TAX that double-counts withholding.

## Fee/Tax relations

Only manual FEE/TAX expose optional related_transaction_id. The parent must exist within the same Account and cannot be FEE or TAX. A missing or wrong-Account parent is indistinguishable (404); invalid parent type, direct self-reference on correction, and incompatible non-null Instruments are invalid input (422). If both child and parent have an Instrument, they must match. A null child Instrument remains account-level and is not inferred from the parent. The currencies may differ. Multiple Fee/Tax children may reference one parent.

The relation records provenance/context only. It does not merge monetary legs, rewrite the parent, change signs, allocate fees/taxes into acquisition basis, modify F005 gross realised P&L, or perform FX conversion. Each transaction retains its own currency, amount and effective date.

## Corrections and deletion

All eight types are editable current best-known canonical facts. Persisted type is authoritative and immutable, as are ID, Account, created_at and note. Success explicitly refreshes UTC updated_at; rejection changes neither facts nor lifecycle metadata. Existing strong create validation is reused. Cash-flow corrections replace date/currency/cash; income corrections also replace required Instrument; Fee/Tax corrections replace both optional Instrument and relation, with explicit null clearing either. Trade corrections retain F002 independent quantity, price and cash and required-but-nullable settlement_date.

Hard deletion removes the canonical event. Derived holdings, FIFO matches or realised results do not prevent correction/deletion. Inbound canonical relations remain protected by the existing restrictive FK: conflict is 409, with rollback and no deletion, cascade, detachment or automatic nulling. Clear/change the child relation or delete the child explicitly before deleting its parent. Current history is reconstructed on subsequent reads, including historical results.

## Consequences

F006's original correction-type and uneditable-relation restrictions are extended only for the newly supported manual types and editable Fee/Tax relation. No reversal, soft deletion, audit/revision model, net-income calculation, net/fee-adjusted P&L, tax engine, FX, settled cash accounting, imports or new financial semantics are introduced.

# Decision F008 — Cash and income/outflow reconstruction

## Decision

Money is computed from canonical Account history for an explicit as_of_date. Include transactions exactly when effective_date <= as_of_date. Settlement dates are ignored: recorded cash is not broker-reported available cash or settled cash. Order does not change sums. Reconstruct each Account independently; Portfolio aggregation combines those Account summaries only within each currency, without an FX total.

Cash effects use factual cash_amount, never quantity × price:

```text
DEPOSIT +cash; WITHDRAWAL -cash; BUY -cash; SELL +cash;
DIVIDEND +cash; COUPON +cash; FEE -cash; TAX -cash.
```

Every current type has an explicit rule. Unknown future types and malformed canonical cash/currency or impossible canonical state fail explicitly as internal reconstruction invariants; do not silently skip them or substitute zero. Negative cash is valid. Preserve an active currency bucket even when its balance is exactly zero. No included transactions means an empty currency collection, not a guessed zero balance.

## Exactness and output

Canonical cash uses scale eight. Reconstruction uses arbitrary-size integer units of 10^-8 and exact context-independent conversion. Do not accumulate in ambient Decimal context, use binary floating point, round, truncate, or quantize away factual precision. Aggregate totals may exceed NUMERIC(24,8) input capacity and must remain exact.

Each active currency exposes: currency_code, cash_balance, deposits, withdrawals, buy_trade_cash_outflow, sell_trade_cash_inflow, gross_dividend_income, gross_coupon_income, gross_investment_income, fees_paid, taxes_paid_or_withheld. Category totals are positive magnitudes; only cash_balance applies directional signs. Gross investment income is exactly gross dividend plus gross coupon income. Fees and taxes are separate totals, not a combined expense, net income or net P&L metric.

Public amounts are normalized ordinary decimal strings with at most eight fractional digits: no exponent, leading plus, unnecessary integer zeroes, trailing fractional zeroes or negative zero; exact zero is `"0"`. Derived integer parts are not restricted to canonical storage width. Output currencies are sorted ascending. F005's exact rational wire representation and GROSS_TRADE_CASH_REALISED_PNL methodology remain unchanged; Fee/Tax affect Money but not gross trade-cash realised P&L.

## Consequences

Money remains reconstruct-on-read with no snapshot, cache, materialized balance or database migration. Corrections/deletions cause deterministic reconstruction from current history. No cash sufficiency, settled-cash model, FX, tax liability, valuation, performance, net-income/net-P&L or fee-to-basis treatment is defined.

# Decision F009 — Market-price valuation and unrealised P&L reconstruction

## Decision

Valuation and unrealised P&L are recomputable derived financial state.

Canonical Transaction history remains the accounting source of truth for position quantity and acquisition basis.

Market-price observations are separate factual market-data inputs used only for valuation and do not become accounting Transactions.

### Manual market-price observations

A manual market-price observation identifies:

- one canonical Instrument;
- an exact direct monetary unit price;
- one price currency;
- an effective date.

Market price MUST be greater than or equal to zero.

Negative market prices are outside F009.

A zero market price is valid.

The observation price represents monetary value per canonical Instrument quantity unit.

F009 does not define percentage-of-par bond quotation, clean/dirty price, accrued interest, contract multipliers or another non-direct quotation system.

The observation effective date is the date for which the market price is financially applicable.

F009 introduces no intraday price-time methodology.

Technical creation or insertion time does not determine valuation.

### Price selection

For valuation as of date `D`, select the latest known market-price observation for the Instrument whose effective date is less than or equal to `D`.

No future observation may be used.

No interpolation is performed.

BUY/SELL `price`, `cash_amount / quantity` or another Transaction fact MUST NOT be used as an implicit fallback market price.

If a non-zero position has no applicable price observation, market value and unrealised P&L are unresolved with reason:

`MISSING_MARKET_PRICE`

F009 defines no price-staleness threshold.

The effective date of the selected observation remains part of the valuation provenance.

### Market value

Let:

- `Q` be the F003 reconstructed position quantity as of `D`;
- `P` be the selected applicable market price.

For a non-zero priced position:

`market value = Q × P`

The result is denominated in the selected market-price currency.

For `Q > 0`, market value is positive when price is positive.

For `Q = 0`, market value is exactly zero and no market-price observation is required.

For `Q < 0`, a selected market price produces a negative signed market value.

Computing signed market value for a negative reconstructed position does not establish short-selling cost-basis or short unrealised-P&L methodology.

### Long-position unrealised P&L

Unrealised P&L uses F004 remaining acquisition lots and remaining acquisition basis as of the same date `D`.

For an open supported long lot with:

- remaining quantity `q`;
- remaining acquisition basis `B`;
- selected market price `P`;

the lot market value is:

`lot market value = q × P`

If the lot acquisition-basis currency equals the selected market-price currency:

`lot unrealised P&L = lot market value - remaining acquisition basis`

The result is exact and denominated in that shared currency.

Positive results are unrealised gains.

Negative results are unrealised losses.

Zero is valid.

Only remaining open basis participates.

Acquisition basis already removed by realised SELL disposal does not participate in unrealised P&L.

### Mixed basis currencies

A selected market price has one currency.

If an open lot's remaining acquisition-basis currency differs from the selected price currency, numeric unrealised P&L for that lot is unresolved with reason:

`CURRENCY_MISMATCH`

The marked value and acquisition-basis facts remain preserved independently.

Other open lots of the same Instrument whose basis currency matches the price currency may still produce resolved unrealised P&L.

A single Instrument may therefore have partially resolved unrealised P&L.

### Unmatched SELL and incomplete long basis

If the as-of F004 reconstruction contains unmatched SELL quantity while F003 reports a positive net position, F009 MUST NOT treat all remaining F004 BUY lots as the acquisition basis of that net position.

In this state current long-position unrealised P&L is unresolved with reason:

`MISSING_ACQUISITION_BASIS`

F009 does not match later BUY lots retroactively to earlier unmatched SELLs and does not invent short-cover methodology.

### Negative positions

For a negative F003 position quantity, market value may still be calculated as the signed quantity multiplied by an applicable market price.

Unrealised P&L is unresolved with reason:

`UNSUPPORTED_NEGATIVE_POSITION`

F009 does not define short-sale acquisition basis, borrow, margin or short-cover P&L.

### Zero positions

A zero reconstructed position has:

- market value = 0;
- current unrealised P&L = 0.

No market price is required.

This does not resolve historical realised-P&L or short-accounting questions; it only defines current valuation for zero net quantity.

### Currency aggregation

Market value and resolved unrealised P&L aggregate only within identical currencies.

Different currencies MUST NOT be added or converted without separate FX methodology.

Account reconstruction occurs independently before Portfolio aggregation.

Portfolio results remain partitioned by currency.

If unresolved valuation or unrealised components exist, resolved currency subtotals remain usable but MUST NOT be represented as complete totals.

### Interaction with existing financial events

F009 does not modify F004 or F005.

FEE and TAX do not modify F009 remaining acquisition basis.

DIVIDEND and COUPON do not modify position market value or acquisition basis.

Gross realised trade-cash P&L is separate from unrealised P&L and is not added into F009 calculations.

Cash, DEPOSIT and WITHDRAWAL are not included in F009 security market value.

F009 therefore does not define total Portfolio NAV or net liquidation value.

### Exact arithmetic

Market-price input must preserve its exact factual decimal value without binary floating point or silent rounding.

Market value is the exact product of quantity and price.

F004 remaining acquisition basis remains exact rational financial state.

Same-currency unrealised P&L is the exact subtraction of marked value and remaining basis.

Aggregation uses exact arithmetic within each currency.

No financial display rounding, Decimal-context rounding, silent truncation or cross-currency conversion is part of F009.

### Recalculation

Valuation and unrealised P&L are fully recomputable as-of-date derived state.

Backdated Transaction changes may alter F003 positions and F004 remaining basis.

Backdated, corrected or newly available market-price observations may alter the selected as-of price.

Derived valuation results always reflect the current canonical financial history and current applicable market-price observations.

## Reason

F003 and F004 already provide exact reconstructed quantity and long-position acquisition basis.

A manual market-price observation provides the only additional fact required to mark an open security position without introducing an external market-data provider.

Selecting the latest observation not later than the valuation date avoids look-ahead and permits historical as-of valuation without interpolation.

Using explicit price currency and preserving currency partitions avoids implicit FX.

Separating market value from unrealised-P&L resolution permits factual signed valuation of negative quantities while correctly refusing to invent unsupported short-position basis.

Per-lot same-currency unrealised P&L also preserves usable resolved results where other lots require FX.

Explicit unresolved states prevent missing market prices, incomplete acquisition basis and currency mismatches from being misrepresented as zero.

## Consequences

The financial domain may reconstruct as-of security market value and long-position unrealised P&L without valuation providers, FX or performance methodology.

Market value uses F003 quantity and the latest applicable manual price observation.

Zero positions value to zero without requiring a price.

Negative positions can have signed market value but do not receive short-position unrealised P&L.

Supported long-position unrealised P&L uses only remaining F004 basis.

Missing prices, unmatched long-basis history and currency mismatches remain explicit unresolved states.

Same-currency resolved market values and unrealised results may aggregate by Account and Portfolio while currencies remain partitioned.

Fees, taxes, dividends, coupons, cash and realised P&L remain separate financial dimensions.

F009 does not define database schema, public API, frontend presentation, external quote providers, automatic price import, FX conversion, total Portfolio NAV, performance, TWR, XIRR or benchmark methodology.

---

# Decision F010 — Portfolio value and time-weighted performance

**Decision**

Decision F010 defines Portfolio Performance Value and time-weighted performance for an inclusive requested period:

```text
[S, E]
```

The calculation uses canonical accounting history and previously approved reconstruction/valuation semantics.

## Performance Value

For each date `d`, Portfolio Performance Value is:

```text
V_d =
canonical F008 cash
+
F009 signed security market value
```

Performance Value must NOT separately add:

- cost basis;
- realised P&L;
- unrealised P&L;
- Dividend totals;
- Coupon totals.

These values must not be added as additional Portfolio value components.

BUY/SELL, income, fees, taxes, security holdings and cash already affect the canonical cash/security state through their approved semantics.

## External owner flows

For Performance & TWR v1, the only external owner flows are:

- `DEPOSIT`;
- `WITHDRAWAL`.

For each date `d`, all external owner flows on that date are netted into one signed external flow:

```text
F_d
```

Direction:

```text
DEPOSIT    → positive F_d
WITHDRAWAL → negative F_d
```

Same-day external flows are treated as occurring at the start of the day.

The following are NOT external owner flows:

- BUY;
- SELL;
- DIVIDEND;
- COUPON;
- FEE;
- TAX.

BUY and SELL are internal transformations between canonical cash and security position.

DIVIDEND and COUPON increase performance through their actual canonical cash effect.

FEE and TAX reduce performance through their actual canonical cash effect.

Therefore v1 TWR is after actually recorded FEE/TAX cash effects.

Decision F010 does NOT introduce a separate gross-before-fees or gross-before-tax TWR metric.

## Requested period

The requested period is inclusive:

```text
[S, E]
```

The opening Portfolio Performance Value is:

```text
V_(S-1)
```

Performance reconstruction therefore requires the state immediately before `S`.

`V_(S-1)` is a required Performance Value. If `V_(S-1) < 0`, the requested
performance is unresolved as `NEGATIVE_PERFORMANCE_VALUE`. First-day external
flow does not make such a period resolved, even if the adjusted first-day
capital base and closing value are positive.

For every date `d` in `[S,E]`, define the adjusted capital base:

```text
A_d = V_(d-1) + F_d
```

## Daily growth factor — positive capital base

If:

```text
A_d > 0
```

and:

```text
V_d >= 0
```

then:

```text
G_d = V_d / A_d
```

This includes the case:

```text
V_d = 0
```

which produces:

```text
G_d = 0
```

and therefore represents a `-100%` growth factor for that day.

A zero market price is valid under the approved F009 valuation semantics.

Therefore a valid zero market price may legitimately produce zero signed security market value, zero Portfolio Performance Value, and a `-100%` daily growth factor when the capital base is positive.

## Daily growth factor — zero capital and zero value

If:

```text
A_d = 0
```

and:

```text
V_d = 0
```

then:

```text
G_d = 1
```

This is a neutral day.

In particular, a complete external withdrawal that leaves both:

```text
adjusted capital base = 0
```

and:

```text
closing Portfolio Performance Value = 0
```

produces:

```text
G_d = 1
```

This neutral day does NOT reset, erase, or replace TWR accumulated on earlier dates in the requested period.

It contributes a multiplicative factor of `1` to the requested-period TWR chain.

## Unresolved — non-positive capital base

If:

```text
A_d < 0
```

the requested performance is unresolved as:

```text
NON_POSITIVE_CAPITAL_BASE
```

No growth factor is invented for that date.

## Unresolved — zero capital base with positive value

If:

```text
A_d = 0
```

and:

```text
V_d > 0
```

the requested performance is unresolved as:

```text
ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE
```

No infinite, synthetic, or fallback growth factor is reported.

## Unresolved — negative Performance Value

If:

```text
V_d < 0
```

the requested performance is unresolved as:

```text
NEGATIVE_PERFORMANCE_VALUE
```

Negative cash by itself does NOT make performance unresolved.

Negative canonical cash is allowed when the total:

```text
Performance Value =
cash + signed security market value
```

remains non-negative and the adjusted capital base remains valid under the rules above.

The unresolved condition is based on total `V_d`, not merely on the cash component.

## No capital at risk

If the entire requested period contains no date for which:

```text
A_d > 0
```

the requested-period return MUST NOT be reported as `0%`.

It is unresolved as:

```text
NO_CAPITAL_AT_RISK
```

The absence of capital at risk is not interpreted as zero investment performance.

## Requested-period TWR

When the requested period resolves under the rules above, TWR is:

```text
TWR =
product(G_d for every d in [S,E])
-
1
```

The chain includes every date in the requested period according to the approved daily rules.

There is no partial requested-period TWR fallback.

If a required date cannot be resolved, the requested-period TWR is unresolved.

The implementation must NOT:

- skip the unresolved date;
- shorten the requested period silently;
- return TWR for only the resolvable suffix/prefix;
- substitute a neutral growth factor unless the explicit `A_d = 0 && V_d = 0` rule applies.

## Single-currency performance

Performance v1 is single-currency only.

All canonical cash and signed security market values required for one Performance Value must be resolvable in one common performance currency without introducing an unapproved FX conversion.

If Portfolio Performance Value requires FX conversion that is not available under approved methodology, requested performance is unresolved as:

```text
MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX
```

Decision F010 does not define:

- FX conversion;
- FX-rate selection;
- FX settlement semantics;
- FX P&L.

## Missing market price

Performance Value reuses F009 market-price and signed-market-value semantics.

If a market price required to resolve signed security market value is missing, requested value/performance is unresolved as:

```text
MISSING_MARKET_PRICE
```

No future price is used.

No interpolation is introduced by F010.

No BUY/SELL fallback price is introduced by F010.

## Interaction with other F009 unresolved results

F009 outcomes:

- `CURRENCY_MISMATCH`;
- `MISSING_ACQUISITION_BASIS`;
- `UNSUPPORTED_NEGATIVE_POSITION`;

do NOT block TWR merely because those F009 outcomes exist.

They block performance only if the signed security market value required by F010 cannot itself be resolved.

In particular:

- TWR does not require cost-basis resolution;
- TWR does not require realised-P&L resolution;
- TWR does not require unrealised-P&L resolution.

If signed security market value resolves, Performance Value may resolve even when another F009-derived result does not.

## Exact arithmetic

Performance calculations use exact arithmetic.

Money follows the project's existing exact-money semantics.

Dimensionless performance ratios use exact rational arithmetic.

This includes:

- daily `G_d`;
- requested-period TWR.

Canonical performance calculation must not use binary floating-point arithmetic.

No silent rounding is introduced by Decision F010.

## Historical recomputation

Performance is derived state, not an independent canonical source of truth.

Backdated changes to canonical history must affect historical performance when applicable.

This includes:

- creation of backdated Transactions;
- correction of historical Transactions;
- deletion of historical Transactions where existing canonical correction semantics allow deletion;
- addition of historical MarketPriceObservation records;
- correction/change of historical MarketPriceObservation records.

Affected historical Portfolio values and requested-period performance must be recomputed from the resulting canonical facts and approved methodology.

Decision F010 does not introduce persisted performance snapshots that override canonical reconstruction.

## Explicit unresolved reason vocabulary

Decision F010 uses the following performance unresolved reasons:

```text
MISSING_MARKET_PRICE
MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX
NON_POSITIVE_CAPITAL_BASE
ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE
NEGATIVE_PERFORMANCE_VALUE
NO_CAPITAL_AT_RISK
```

These reason codes represent the approved financial conditions defined above.

They are not placeholders for alternative fallback calculations.

## Explicitly deferred

Decision F010 does not define:

- XIRR;
- FX conversion;
- multi-currency performance through FX;
- risk-adjusted performance;
- volatility;
- drawdown methodology;
- benchmark methodology except through a separate approved Decision.

**Reason**

Portfolio performance must measure the change in economic Portfolio value while neutralizing external owner capital movements.

Using:

```text
canonical F008 cash
+
F009 signed security market value
```

provides the required Performance Value without double counting derived accounting results.

Only DEPOSIT/WITHDRAWAL are external owner flows because BUY/SELL and income/expense transactions operate inside the Portfolio's economic state.

The start-of-day treatment for already-netted same-day external flows gives one deterministic v1 timing convention without introducing intraday performance methodology.

Explicit capital-base/value conditions prevent undefined or misleading returns from being silently represented as valid TWR.

Exact rational arithmetic preserves the project's exact financial-calculation policy.

**Consequences**

Portfolio TWR can be reconstructed from canonical history plus approved cash, quantity and market-value semantics.

Cost basis, realised P&L and unrealised P&L are not required inputs to performance.

Actually recorded FEE/TAX reduce performance through cash, while actually recorded DIVIDEND/COUPON increase performance through cash.

A complete withdrawal to zero value produces a neutral daily factor rather than deleting prior performance history.

A zero market price remains valid and can legitimately produce a `-100%` daily growth factor.

Negative cash is not independently disqualifying if total Performance Value and adjusted capital base remain valid.

Requested-period TWR is all-or-unresolved; there is no partial-period fallback.

Historical canonical corrections and historical price changes recompute derived historical performance.

Performance remains single-currency until an FX methodology is approved.

XIRR remains deferred.

---

# Decision F011 — Single-instrument benchmark simulation and comparison

**Decision**

Decision F011 defines the v1 benchmark as one manually selected canonical Instrument.

The benchmark is a frictionless, price-only simulation using existing canonical MarketPriceObservation data and approved F009 price-selection semantics.

The benchmark is calculated for the same requested period:

```text
[S, E]
```

as Portfolio performance under Decision F010.

## Benchmark Instrument

The benchmark consists of exactly one selected canonical Instrument.

The benchmark must use the same currency as the Portfolio performance calculation.

No FX conversion is introduced.

Benchmark v1 does not model:

- benchmark dividends;
- benchmark coupons;
- benchmark fees;
- benchmark taxes;
- corporate actions;
- total-return adjustments.

It is a price-only benchmark.

## Benchmark prices

Let:

```text
B_d
```

be the selected benchmark Instrument price applicable to date `d`.

`B_d` uses the existing F009 latest-applicable MarketPriceObservation semantics.

Therefore benchmark price selection preserves all of the following:

- use the latest applicable observation with effective date `<= d`;
- never use a future benchmark price;
- no interpolation;
- no first-price-after-date fallback;
- no inferred BUY/SELL price;
- no independently invented benchmark pricing rule.

If a benchmark price required by the approved simulation cannot be selected because no applicable MarketPriceObservation exists, the benchmark is unresolved as:

```text
MISSING_BENCHMARK_MARKET_PRICE
```

If the benchmark price currency is incompatible with the Portfolio performance currency and resolving the comparison would require FX, the benchmark is unresolved as:

```text
BENCHMARK_CURRENCY_MISMATCH
```

No FX conversion is inferred.

## Opening benchmark value

The benchmark starts with the actual Portfolio opening Performance Value:

```text
V_(S-1)
```

There is no independently chosen benchmark starting capital.

### Positive opening Portfolio value

If:

```text
V_(S-1) > 0
```

then an applicable benchmark opening price:

```text
B_(S-1)
```

must exist.

It MUST also be strictly positive:

```text
B_(S-1) > 0
```

Initial benchmark units are:

```text
U_(S-1) =
V_(S-1) / B_(S-1)
```

If the required opening benchmark price is missing:

```text
MISSING_BENCHMARK_MARKET_PRICE
```

If:

```text
B_(S-1) = 0
```

the benchmark cannot create opening units and is unresolved as:

```text
ZERO_BENCHMARK_OPENING_PRICE
```

A zero benchmark price is valid as a valuation price, but it is not valid as the denominator for opening benchmark-unit creation.

### Zero opening Portfolio value

If:

```text
V_(S-1) = 0
```

then:

```text
U_(S-1) = 0
```

No opening benchmark purchase is required.

Opening zero capital must not be transformed into an artificial benchmark position.

## Same external owner flows

The benchmark receives exactly the same external owner flows used by F010:

```text
F_d
```

Same-day external flows are already netted according to F010.

F011 does not reclassify or renet them using another methodology.

Only F010 DEPOSIT/WITHDRAWAL external owner flows affect benchmark-unit creation/redemption.

## Flow execution price

For every non-zero external flow:

```text
F_d != 0
```

the benchmark execution price is:

```text
B_(d-1)
```

The applicable:

```text
B_(d-1)
```

must exist and MUST be strictly positive.

If the required benchmark flow-execution price is missing:

```text
MISSING_BENCHMARK_MARKET_PRICE
```

If:

```text
B_(d-1) = 0
```

for a non-zero external flow, the benchmark is unresolved as:

```text
ZERO_BENCHMARK_FLOW_EXECUTION_PRICE
```

A zero benchmark price remains valid for valuation, but it cannot be used as a denominator to execute a non-zero simulated owner flow.

For a non-zero flow, benchmark units evolve as:

```text
U_d =
U_(d-1)
+
F_d / B_(d-1)
```

For a date with:

```text
F_d = 0
```

there is no simulated flow execution and no division by `B_(d-1)` for flow creation/redemption.

Benchmark units remain unchanged by owner flow on that date.

## No negative benchmark units

After applying the external flow for date `d`, benchmark units must not be negative.

If:

```text
U_d < 0
```

the benchmark is unresolved as:

```text
BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE
```

Benchmark v1 does not support:

- negative benchmark units;
- benchmark shorting;
- leveraged benchmark exposure.

A withdrawal cannot create a synthetic short benchmark position.

## Benchmark valuation

For each resolved date:

```text
W_d =
U_d × B_d
```

where:

- `U_d` is the exact simulated benchmark-unit quantity after the start-of-day flow;
- `B_d` is the F009-selected benchmark valuation price;
- `W_d` is benchmark value.

A benchmark price of zero is valid for valuation.

Therefore:

```text
B_d = 0
```

may validly produce:

```text
W_d = 0
```

provided the zero price is not being used as a denominator for opening-unit creation or a non-zero simulated flow.

## Benchmark TWR

Benchmark TWR uses the same F010 time-weighted-performance methodology.

F011 does NOT define a separate benchmark-return formula.

The benchmark uses:

- its opening value;
- the same F010 external owner flows;
- its simulated daily benchmark values.

The applicable F010 capital-base and TWR rules therefore remain the return methodology for the simulated benchmark path.

## Portfolio performance prerequisite

Benchmark comparison is defined relative to Portfolio performance.

If Portfolio performance for the requested period is unresolved, the Portfolio-vs-benchmark comparison MUST NOT be presented as resolved.

The benchmark comparison outcome is unresolved as:

```text
UNRESOLVED_PORTFOLIO_PERFORMANCE
```

No active return or resolved comparative result is reported against an unresolved Portfolio TWR.

In particular, a negative required Portfolio opening value `V_(S-1)` produces
`UNRESOLVED_PORTFOLIO_PERFORMANCE`. No opening benchmark units are constructed:
neither zero units nor negative units are used as a fallback.

## Comparison outputs

When both Portfolio performance and benchmark performance resolve:

```text
active_return =
PortfolioTWR - BenchmarkTWR
```

At requested period end:

```text
ending_value_difference =
Portfolio ending Performance Value
-
benchmark ending value
```

No other comparison methodology is implied by Decision F011.

## Exact arithmetic

Benchmark calculations preserve exact arithmetic throughout.

Benchmark units:

```text
U_d
```

are exact rational quantities.

Benchmark values:

```text
W_d
```

are exact.

Benchmark TWR is an exact rational quantity.

`active_return` is an exact rational quantity.

`ending_value_difference` is exact money.

The benchmark calculation must not use binary floating-point arithmetic as canonical methodology.

It must not silently:

- round;
- truncate;
- approximate benchmark units;
- approximate ratios;
- approximate ending-value difference.

## Benchmark unresolved reason vocabulary

Decision F011 defines the following benchmark unresolved reasons:

```text
UNRESOLVED_PORTFOLIO_PERFORMANCE
MISSING_BENCHMARK_MARKET_PRICE
BENCHMARK_CURRENCY_MISMATCH
ZERO_BENCHMARK_OPENING_PRICE
ZERO_BENCHMARK_FLOW_EXECUTION_PRICE
BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE
ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE
```

Their financial conditions are:

### UNRESOLVED_PORTFOLIO_PERFORMANCE

Portfolio performance required for comparison is itself unresolved.

The comparison must not be presented as resolved.

### MISSING_BENCHMARK_MARKET_PRICE

A benchmark price required by the approved opening, flow-execution, valuation, or benchmark-performance calculation has no applicable F009 MarketPriceObservation.

No future price or interpolation is substituted.

### BENCHMARK_CURRENCY_MISMATCH

The benchmark price currency does not match the Portfolio performance currency and resolving it would require unapproved FX conversion.

### ZERO_BENCHMARK_OPENING_PRICE

Opening Portfolio value is positive, but:

```text
B_(S-1) = 0
```

so initial benchmark units cannot be created through division by the opening benchmark price.

### ZERO_BENCHMARK_FLOW_EXECUTION_PRICE

There is a non-zero external owner flow on date `d`, but:

```text
B_(d-1) = 0
```

so the simulated benchmark flow cannot be executed without division by zero.

### BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE

Applying the external withdrawal would produce:

```text
U_d < 0
```

which would require unsupported negative benchmark units.

### ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE

If benchmark adjusted capital base is zero while benchmark closing value is positive, benchmark TWR is unresolved under the same F010 rule as Portfolio TWR.

```text
W_(d-1) + F_d = 0
and
W_d > 0
→ ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE
```

This includes benchmark price recovery above zero after a valid zero-price day, with no external flow. The prior `-100%` must not be preserved as a resolved requested-period result; the recovery date must not be skipped or assigned `G = 1`. `UNRESOLVED_PORTFOLIO_PERFORMANCE` must not be used when Portfolio performance itself is resolved.

## Explicitly deferred

Decision F011 does not define:

- multiple benchmark Instruments;
- weighted benchmark portfolios;
- total-return indices;
- benchmark dividend reinvestment;
- benchmark coupon reinvestment;
- benchmark corporate-action handling;
- benchmark fees;
- benchmark taxes;
- benchmark FX conversion;
- benchmark FX P&L;
- short benchmark positions;
- leveraged benchmark exposure;
- tracking error;
- alpha;
- beta;
- volatility;
- other risk analytics;
- persisted benchmark preference.

**Reason**

A single manually selected canonical Instrument is the smallest benchmark capable of providing a useful alternative price path without creating a new benchmark-data model.

Starting with actual Portfolio opening value and applying the same external owner flows makes Portfolio and benchmark outcomes economically comparable.

Using `B_(d-1)` for flow execution mirrors the F010 start-of-day owner-flow convention.

Reusing F009 latest-applicable market-price semantics prevents benchmark calculation from silently developing its own historical price-selection methodology.

A frictionless price-only benchmark deliberately avoids introducing unapproved total-return, corporate-action, FX, fee or tax methodology.

Exact rational benchmark units allow external flows to be simulated without approximation or binary floating-point drift.

**Consequences**

A Portfolio performance request can compare the Portfolio with one selected canonical Instrument.

Both paths start from the same Portfolio opening value and receive the same external owner flows.

Benchmark valuation may legitimately use a zero price, but zero cannot be used as a denominator for positive opening-capital allocation or non-zero external-flow execution.

Withdrawals cannot create negative benchmark units.

Portfolio-vs-benchmark comparison does not resolve when Portfolio performance itself is unresolved.

Benchmark TWR reuses F010 instead of defining a competing return methodology.

`active_return` remains exact rational, while ending-value difference remains exact money.

Benchmark v1 remains a same-currency, price-only simulation.

---

# Decision F012 — Normalized CSV canonical transaction import

## Decision

CSV Import v0.1 imports historical financial events into the existing canonical Transaction history.

It does not create a separate accounting model, import ledger or alternate source of truth.

Imported Transactions have the same financial semantics as manually entered canonical Transactions under F001–F011.

### Supported canonical types

CSV Import v0.1 supports:

- DEPOSIT;
- WITHDRAWAL;
- BUY;
- SELL;
- DIVIDEND;
- COUPON;
- FEE;
- TAX.

The first importer accepts one project-controlled normalized CSV contract.

Broker-specific parsing and mapping are outside F012. Any future broker adapter must normalize source records into the approved canonical CSV contract without changing canonical financial semantics.

### Normalized row identity

Every normalized CSV data row has a file-local `row_id`.

`row_id` MUST be unique within that CSV.

It exists for deterministic import processing, diagnostics and intra-file relationship references.

It is not the canonical Transaction ID.

### Required financial facts

DEPOSIT and WITHDRAWAL require:

- effective date;
- currency;
- positive cash amount.

BUY and SELL require:

- canonical Instrument identity;
- effective date;
- currency;
- positive quantity;
- positive price;
- positive cash amount.

A factual settlement date may additionally be provided for BUY/SELL.

DIVIDEND and COUPON require:

- canonical Instrument identity;
- effective date;
- currency;
- positive gross cash amount.

FEE and TAX require:

- effective date;
- currency;
- positive cash amount.

FEE and TAX may additionally contain:

- canonical Instrument identity;
- an intra-file related-row reference.

All type-specific facts follow the already approved manual-entry semantics.

### Independent trade facts

For BUY and SELL:

- quantity;
- price;
- cash amount

remain independent factual canonical values.

The importer MUST NOT calculate, replace or correct one from either of the others.

In particular it MUST NOT force:

`cash_amount = quantity × price`.

A discrepancy does not by itself invalidate an otherwise canonical-valid trade.

### Dates

Normalized CSV `effective_date` becomes canonical `effective_date` without reinterpretation.

For BUY/SELL it MUST represent the factual trade/execution date.

Settlement or posting dates MUST NOT silently be substituted for an unknown trade date.

If factual settlement date is supplied, it remains a separate settlement fact and must satisfy the approved manual-entry rules.

The importer MUST NOT infer T+1, T+2 or another settlement convention.

### Same-date deterministic ordering

F004 remains authoritative:

`effective_date ASC, then transaction_id ASC`.

Within one CSV import, physical normalized CSV row order is the authoritative import order.

Architecture MUST preserve that row order in the relative canonical transaction-ID ordering of imported transactions sharing the same effective date.

The importer MUST NOT reorder same-date rows by transaction type, Instrument, relationship or another inferred financial rule.

Existing canonical Transactions retain their existing IDs.

New imported Transactions therefore follow existing same-date Transactions according to F004's transaction-ID tie-break and preserve their normalized CSV row order relative to one another.

This rule provides deterministic v0.1 ordering but does not claim to reconstruct unknown intraday chronology.

F012 does not introduce an execution timestamp or separate source-sequence override for F004.

### FEE and TAX relationships

A FEE or TAX may be standalone.

When a normalized FEE/TAX row refers to another row in the same CSV, it uses that row's unique file-local identity.

The relationship is resolved to the resulting canonical Transaction relationship only after the full file has been validated.

The parent may occur before or after the child in file order.

A relationship:

- must remain within the same InvestmentAccount;
- must not reference the transaction itself;
- must not use another FEE/TAX as its originating parent in v0.1;
- may have multiple FEE/TAX children;
- must preserve Instrument consistency when both child and parent identify an Instrument.

A missing, duplicate, ambiguous or invalid specified parent invalidates the entire import.

A relation does not merge or rewrite any monetary amount and does not change cash, F005 or FX semantics.

CSV v0.1 does not create a new relation from an imported row to an already existing canonical Transaction.

### Instrument resolution

The normalized CSV contract identifies Instruments by canonical internal Instrument identity.

The canonical importer MUST NOT guess an Instrument from name, ticker, price, currency or another heuristic.

An Instrument reference must resolve to exactly one existing canonical Instrument.

Missing or ambiguous Instrument identity invalidates the import where Instrument is required.

Future broker-specific mapping from ISIN, ticker, FIGI or other identifiers occurs before canonical CSV import and must itself produce an unambiguous canonical Instrument identity.

### Exact numbers and currencies

All numeric CSV facts are parsed exactly without binary floating point.

Existing canonical precision, scale, range and representability rules remain authoritative.

A value that cannot be represented exactly under those rules is rejected rather than rounded or truncated.

Canonical direction continues to be represented by Transaction type, not by signed input magnitudes.

Currency codes must already satisfy the approved canonical three-uppercase-ASCII-letter representation.

The importer does not silently normalize or convert currencies.

### Duplicate and repeated import semantics

Financial events MUST NOT be deduplicated solely because their transaction fields are equal.

Two identical-looking transactions may represent two distinct factual events.

However, repeated import of the same normalized import source MUST be idempotent.

Re-submitting the same import must leave canonical financial history unchanged and MUST NOT create a second copy of its Transactions.

Architecture must provide stable import identity or equivalent deterministic duplicate-import detection.

The physical mechanism is outside F012.

F012 does not attempt heuristic cross-file transaction reconciliation where stable source identity is unavailable.

### Atomicity

CSV Import v0.1 is whole-file atomic.

Before any canonical Transaction is committed, the complete file must be:

- parsed;
- type-validated;
- financially validated;
- checked for exact numeric representability;
- resolved against canonical Instruments;
- checked for repeated-import identity;
- checked for unique row identities;
- resolved and validated for intra-file FEE/TAX relationships;
- prepared with deterministic row ordering.

If any row or required relationship is invalid or unresolved, no Transaction from the file is committed.

Partial-success import is not permitted in v0.1.

### Existing history and derived state

Imported events are ordinary canonical Transactions.

Historical and backdated import is allowed.

Imported events participate in canonical ordering together with existing manual history.

No special import precedence exists.

Positions, FIFO matching, cost basis, gross realised P&L, money reconstruction, valuation, unrealised result and performance remain derived and recomputable from the resulting current canonical history.

An imported canonical fact is not rejected merely because derived reconstruction later produces an approved unresolved or negative state such as oversell, negative cash, missing acquisition basis or other incomplete-history outcome.

### No corrective inference

CSV Import v0.1 MUST NOT:

- merge trades automatically;
- calculate missing trade amounts from other fields;
- derive FEE or TAX from another monetary amount;
- invent gross income from unsupported net-only income data;
- create FX conversions;
- modify broker/source data based on financial guesses;
- infer missing Instruments;
- infer settlement conventions;
- use future or unrelated financial facts to repair an incomplete row.

If a source cannot be deterministically normalized into approved canonical facts, that source row remains outside CSV v0.1 canonical import.

## Reason

Canonical Transaction history is already the accounting source of truth and all financial calculations are derived from it.

CSV import therefore needs only a deterministic, lossless path for creating the same canonical facts at scale.

Applying existing manual-entry financial semantics prevents imported history from becoming a second accounting convention.

Whole-file atomicity avoids accidental partial histories that could materially alter positions, FIFO, realised P&L, cash and performance.

Explicit file-local row identity allows deterministic intra-file relationships without depending on canonical IDs that do not exist before creation.

Preserving normalized row order for same-date imported events provides deterministic F004 FIFO behavior while acknowledging that the current canonical model has no true intraday chronology.

Stable import idempotency prevents repeated ingestion from silently duplicating financial history, while avoiding unsafe value-based deduplication of genuinely distinct but identical-looking transactions.

## Consequences

Architecture may implement one normalized project-controlled CSV importer that creates ordinary canonical Transactions.

All eight existing canonical transaction types may be imported.

No new financial calculation engine is required.

Architecture must guarantee:

- exact parsing;
- existing canonical validation;
- unambiguous Instrument resolution;
- whole-file atomicity;
- stable repeated-import detection;
- deterministic same-date imported ordering;
- resolution of intra-file FEE/TAX relationships;
- no partial commits;
- no financial inference.

Broker-specific parsing, cross-file reconciliation, source-provenance models, intraday chronology, market-price import, FX and corporate actions remain outside F012.
