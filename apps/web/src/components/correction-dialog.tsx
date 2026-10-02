"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type Entity, type Transaction } from "../lib/api";
import { normalizeDecimal, positiveDecimalError } from "../lib/exact-money";
import { Dialog } from "./dialog";
import { dateError, Field } from "./entry-dialogs";

export function CorrectionDialog({
  transaction,
  instruments,
  deleting,
  onClose,
  onCorrected,
}: {
  transaction: Transaction;
  instruments: Entity[];
  deleting: boolean;
  onClose: () => void;
  onCorrected: () => void;
}) {
  const trade = transaction.type !== "DEPOSIT";
  const [values, setValues] = useState({
    effective_date: transaction.effective_date,
    settlement_date: transaction.settlement_date ?? "",
    currency_code: transaction.currency_code,
    quantity: transaction.quantity ?? "",
    price: transaction.price ?? "",
    cash_amount: transaction.cash_amount,
  });
  const [instrument, setInstrument] = useState(
    String(transaction.instrument_id ?? ""),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const set = (key: keyof typeof values, value: string) =>
    setValues((old) => ({ ...old, [key]: value }));
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    const issues: Record<string, string> = {};
    if (!deleting) {
      const invalidDate = dateError(values.effective_date);
      if (invalidDate) issues.effective_date = invalidDate;
      if (!/^[a-zA-Z]{3}$/.test(values.currency_code.trim()))
        issues.currency_code = "Use exactly 3 Latin letters.";
      for (const key of trade
        ? (["quantity", "price", "cash_amount"] as const)
        : (["cash_amount"] as const)) {
        const issue = positiveDecimalError(
          values[key],
          key === "cash_amount" ? 8 : 12,
        );
        if (issue) issues[key] = issue;
      }
      if (trade) {
        if (!instruments.some((i) => String(i.id) === instrument))
          issues.instrument_id = "Select an Instrument.";
        if (values.settlement_date) {
          const invalidSettlement = dateError(values.settlement_date);
          if (invalidSettlement) issues.settlement_date = invalidSettlement;
          else if (values.settlement_date < values.effective_date)
            issues.settlement_date =
              "Settlement cannot precede the effective date.";
        }
      }
    }
    setErrors(issues);
    setError("");
    if (Object.keys(issues).length) return;
    lock.current = true;
    setBusy(true);
    const request = new AbortController();
    controller.current = request;
    try {
      await api(
        `/accounts/${transaction.account_id}/transactions/${transaction.id}`,
        deleting
          ? undefined
          : {
              effective_date: values.effective_date,
              currency_code: values.currency_code.trim().toUpperCase(),
              cash_amount: normalizeDecimal(values.cash_amount),
              ...(trade
                ? {
                    instrument_id: instruments.find(
                      (i) => String(i.id) === instrument,
                    )!.id,
                    quantity: normalizeDecimal(values.quantity),
                    price: normalizeDecimal(values.price),
                    settlement_date: values.settlement_date || null,
                  }
                : {}),
            },
        request.signal,
        deleting ? "DELETE" : "PUT",
      );
      if (!request.signal.aborted) onCorrected();
    } catch (e) {
      if (!request.signal.aborted) {
        setError(
          e instanceof ApiError && e.status === 409 && deleting
            ? "This entry could not be deleted because a related canonical entry still references it. Nothing was removed."
            : e instanceof Error
              ? e.message
              : "Unable to correct transaction.",
        );
        if (e instanceof ApiError) setErrors(e.fields);
      }
    } finally {
      lock.current = false;
      if (!request.signal.aborted) setBusy(false);
    }
  }
  return (
    <Dialog
      title={deleting ? "Delete transaction" : "Edit transaction"}
      busy={busy}
      onClose={onClose}
    >
      <p>
        {transaction.type} · Transaction #{transaction.id} · Account #
        {transaction.account_id}
      </p>
      <p className="notice">
        {deleting
          ? "This permanently deletes the journal entry. There is no undo."
          : "This replaces the recorded facts in place."}{" "}
        Holdings, FIFO acquisition basis and realised results may change or
        become incomplete. Existing sells do not prevent correction.
      </p>
      <form onSubmit={submit} noValidate>
        {!deleting && (
          <fieldset disabled={busy}>
            {trade && (
              <label>
                Instrument
                <select
                  aria-label="Instrument"
                  value={instrument}
                  onChange={(e) => setInstrument(e.target.value)}
                  aria-invalid={!!errors.instrument_id}
                >
                  <option value="">Select Instrument</option>
                  {instruments.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name} · #{i.id}
                    </option>
                  ))}
                </select>
                {errors.instrument_id && (
                  <span className="field-error">{errors.instrument_id}</span>
                )}
              </label>
            )}
            <div className="form-grid">
              <Field
                label="Effective date"
                name="effective_date"
                type="date"
                value={values.effective_date}
                onChange={(v) => set("effective_date", v)}
                error={errors.effective_date}
              />
              <Field
                label="Currency"
                name="currency_code"
                value={values.currency_code}
                onChange={(v) => set("currency_code", v)}
                error={errors.currency_code}
              />
              {trade && (
                <>
                  <Field
                    label="Quantity"
                    name="quantity"
                    decimal
                    value={values.quantity}
                    onChange={(v) => set("quantity", v)}
                    error={errors.quantity}
                  />
                  <Field
                    label="Price"
                    name="price"
                    decimal
                    value={values.price}
                    onChange={(v) => set("price", v)}
                    error={errors.price}
                  />
                  <Field
                    label="Settlement date (optional)"
                    name="settlement_date"
                    type="date"
                    value={values.settlement_date}
                    onChange={(v) => set("settlement_date", v)}
                    error={errors.settlement_date}
                  />
                </>
              )}
              <Field
                label="Cash amount"
                name="cash_amount"
                decimal
                value={values.cash_amount}
                onChange={(v) => set("cash_amount", v)}
                error={errors.cash_amount}
              />
            </div>
            {trade && (
              <p className="muted">
                Quantity, price and cash amount are independent facts. No
                position or oversell restriction is applied.
              </p>
            )}
          </fieldset>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <footer>
          <button disabled={busy}>
            {busy
              ? "Saving…"
              : deleting
                ? "Delete permanently"
                : "Save changes"}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
