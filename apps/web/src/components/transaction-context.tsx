import { useState } from "react";
import type { Entity, Transaction } from "../lib/api";

export const transactionLabels: Record<string, string> = {
  DEPOSIT: "Deposit",
  WITHDRAWAL: "Withdrawal",
  BUY: "Buy",
  SELL: "Sell",
  DIVIDEND: "Dividend",
  COUPON: "Coupon",
  FEE: "Fee",
  TAX: "Tax",
};
export const transactionPaths: Record<string, string> = {
  DEPOSIT: "deposits",
  WITHDRAWAL: "withdrawals",
  BUY: "buys",
  SELL: "sells",
  DIVIDEND: "dividends",
  COUPON: "coupons",
  FEE: "fees",
  TAX: "taxes",
};
export const isTrade = (type: string) => type === "BUY" || type === "SELL";
export const isIncome = (type: string) =>
  type === "DIVIDEND" || type === "COUPON";
export const isCharge = (type: string) => type === "FEE" || type === "TAX";

export function relationLabel(transaction: Transaction, instruments: Entity[]) {
  const instrument = instruments.find(
    (item) => item.id === transaction.instrument_id,
  );
  return `${transactionLabels[transaction.type] ?? transaction.type} · ${transaction.effective_date}${transaction.instrument_id === null ? "" : ` · ${instrument?.name ?? "Instrument"} #${transaction.instrument_id}`} · ${transaction.cash_amount} ${transaction.currency_code} · #${transaction.id}`;
}

export function relationError(
  history: Transaction[],
  related: string,
  instrument: string,
) {
  if (!related) return undefined;
  const parent = history.find(
    (transaction) => String(transaction.id) === related,
  );
  if (!parent || isCharge(parent.type))
    return "Select an available originating transaction.";
  if (
    instrument &&
    parent.instrument_id !== null &&
    String(parent.instrument_id) !== instrument
  )
    return "Instrument must match the related transaction Instrument.";
  return undefined;
}

export function IncomeHelp({ type }: { type: string }) {
  return (
    <p className="muted">
      Enter the gross {type === "DIVIDEND" ? "dividend" : "coupon"} before
      withholding tax. Record known withholding separately as Tax.
      <br />
      If you only know the net amount, this event cannot be recorded accurately
      yet.
    </p>
  );
}

export function RelationPicker({
  history,
  instruments,
  value,
  onChange,
  error,
  type,
  excludeId,
}: {
  history: Transaction[];
  instruments: Entity[];
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type: string;
  excludeId?: number;
}) {
  const [search, setSearch] = useState("");
  const candidates = history.filter(
    (item) => !isCharge(item.type) && item.id !== excludeId,
  );
  return (
    <div className="relation-picker">
      <label>
        Search related transactions
        <input
          aria-label="Search related transactions"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <label>
        Related transaction (optional)
        <select
          aria-label="Related transaction (optional)"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={!!error}
          aria-describedby={error ? "relation-error" : "relation-help"}
        >
          <option value="">None — standalone</option>
          {candidates
            .filter(
              (item) =>
                String(item.id) === value ||
                relationLabel(item, instruments)
                  .toLowerCase()
                  .includes(search.toLowerCase()),
            )
            .map((item) => (
              <option key={item.id} value={item.id}>
                {relationLabel(item, instruments)}
              </option>
            ))}
        </select>
      </label>
      {error && (
        <p className="field-error" id="relation-error">
          {error}
        </p>
      )}
      <p className="muted" id="relation-help">
        Optional: link this{" "}
        {type === "FEE"
          ? "fee to the transaction that caused it"
          : "tax to the income event or transaction that caused it"}
        . The link adds context only.
        <br />
        Linking does not change trade amounts, realised P&amp;L or currency
        handling.
      </p>
    </div>
  );
}
