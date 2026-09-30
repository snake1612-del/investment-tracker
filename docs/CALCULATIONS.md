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
