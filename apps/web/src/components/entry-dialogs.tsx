"use client";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError, type Entity, type Position } from "../lib/api";
import {
  decimalUnits,
  normalizeDecimal,
  positiveDecimalError,
} from "../lib/exact-money";
import { Dialog } from "./dialog";

export function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function dateError(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000"))
    return "Enter a valid date.";
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ||
    date.toISOString().slice(0, 10) !== value
    ? "Enter a valid date."
    : undefined;
}

export function Field({
  label,
  name,
  value,
  onChange,
  error,
  type = "text",
  decimal = false,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: string;
  decimal?: boolean;
}) {
  return (
    <label>
      {label}
      <input
        aria-label={label}
        name={name}
        type={type}
        inputMode={decimal ? "decimal" : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error}
        aria-describedby={error ? `${name}-error` : undefined}
      />
      {error && (
        <span className="field-error" id={`${name}-error`}>
          {error}
        </span>
      )}
    </label>
  );
}

export function EntityDialog({
  kind,
  portfolioId,
  onClose,
  onCreated,
}: {
  kind: "Portfolio" | "Account";
  portfolioId: number | null;
  onClose: () => void;
  onCreated: (entity: Entity) => void;
}) {
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    const issues: Record<string, string> = {};
    if (!name.trim()) issues.name = "Name is required.";
    if (kind === "Portfolio" && !/^[a-zA-Z]{3}$/.test(currency.trim()))
      issues.base_currency = "Use exactly 3 Latin letters.";
    setErrors(issues);
    setError("");
    if (Object.keys(issues).length) return;
    submitting.current = true;
    setBusy(true);
    try {
      const entity = await api<Entity>(
        kind === "Portfolio"
          ? "/portfolios"
          : `/portfolios/${portfolioId}/accounts`,
        kind === "Portfolio"
          ? { name: name.trim(), base_currency: currency.trim().toUpperCase() }
          : { name: name.trim() },
      );
      onCreated(entity);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create.");
      if (e instanceof ApiError) setErrors(e.fields);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Create ${kind}`} busy={busy} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <fieldset disabled={busy}>
          <Field
            label="Name"
            name="name"
            value={name}
            onChange={setName}
            error={errors.name}
          />
          {kind === "Portfolio" && (
            <Field
              label="Base currency"
              name="base_currency"
              value={currency}
              onChange={setCurrency}
              error={errors.base_currency}
            />
          )}
        </fieldset>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <footer>
          <button disabled={busy}>
            {busy ? "Creating…" : `Create ${kind}`}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}

export function TransactionDialog({
  accountId,
  instruments,
  positions,
  onClose,
  onRecorded,
  onInstrumentCreated,
}: {
  accountId: number;
  instruments: Entity[];
  positions: Position[];
  onClose: () => void;
  onRecorded: () => void;
  onInstrumentCreated: (instrument: Entity) => void;
}) {
  const [type, setType] = useState("DEPOSIT");
  const [values, setValues] = useState({
    effective_date: localDate(),
    currency_code: "",
    quantity: "",
    price: "",
    cash_amount: "",
  });
  const [instrument, setInstrument] = useState("");
  const [search, setSearch] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const trade = type !== "DEPOSIT";
  const current = positions.find((p) => String(p.instrument_id) === instrument);
  const requested = decimalUnits(values.quantity);
  const held = decimalUnits(current?.quantity ?? "0");
  const oversell =
    type === "SELL" && requested !== null && held !== null && requested > held;
  const set = (key: keyof typeof values, value: string) =>
    setValues((old) => ({ ...old, [key]: value }));
  async function createInstrument() {
    if (lock.current) return;
    const name = search.trim();
    if (!name || [...name].length > 200) {
      setError("Instrument name must contain 1–200 characters.");
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const created = await api<Entity>("/instruments", { name });
      onInstrumentCreated(created);
      setInstrument(String(created.id));
      setSearch("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create Instrument.");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    const issues: Record<string, string> = {};
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
    if (trade && !instruments.some((i) => String(i.id) === instrument))
      issues.instrument_id = "Select an Instrument.";
    setErrors(issues);
    setError("");
    if (Object.keys(issues).length) return;
    lock.current = true;
    setBusy(true);
    try {
      await api(
        `/accounts/${accountId}/${type === "DEPOSIT" ? "deposits" : type === "BUY" ? "buys" : "sells"}`,
        {
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
              }
            : {}),
        },
      );
      onRecorded();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to record transaction.",
      );
      if (e instanceof ApiError) setErrors(e.fields);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  const visible = instruments.filter(
    (i) =>
      String(i.id) === instrument ||
      i.name.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <Dialog title="Record transaction" busy={busy} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <fieldset disabled={busy}>
          <label>
            Transaction type
            <select
              aria-label="Transaction type"
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setErrors({});
                setError("");
              }}
            >
              <option value="DEPOSIT">Deposit</option>
              <option value="BUY">Buy</option>
              <option value="SELL">Sell</option>
            </select>
          </label>
          {trade && (
            <div className="instrument-picker">
              <Field
                label="Search or create Instrument"
                name="instrument-search"
                value={search}
                onChange={setSearch}
              />
              <label>
                Instrument
                <select
                  aria-label="Instrument"
                  value={instrument}
                  onChange={(e) => setInstrument(e.target.value)}
                  aria-invalid={!!errors.instrument_id}
                >
                  <option value="">Select Instrument</option>
                  {visible.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name} · #{i.id}
                    </option>
                  ))}
                </select>
                {errors.instrument_id && (
                  <span className="field-error">{errors.instrument_id}</span>
                )}
              </label>
              <button
                type="button"
                className="secondary"
                onClick={createInstrument}
                disabled={!search.trim() || busy}
              >
                Create Instrument{search.trim() && ` “${search.trim()}”`}
              </button>
            </div>
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
              Quantity, price and cash amount are independent facts. Cash may
              differ from quantity × price.
            </p>
          )}
          {oversell && (
            <p className="notice" role="status">
              This sell exceeds the currently reconstructed position. It may
              create a negative position or an incomplete realised result. You
              can still record it.
            </p>
          )}
        </fieldset>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <footer>
          <button disabled={busy}>
            {busy ? "Recording…" : "Record transaction"}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
