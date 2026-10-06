"use client";
import { useEffect, useRef, useState } from "react";
import { api, type Entity } from "../lib/api";
import { decimalUnits, normalizeDecimal } from "../lib/exact-money";
import { dateError, localDate } from "./entry-dialogs";
import { Dialog } from "./dialog";

type Observation = {
  id: number;
  instrument_id: number;
  price: string;
  currency_code: string;
  effective_date: string;
};

export function MarketPrices({ onChanged }: { onChanged: () => void }) {
  const [instruments, setInstruments] = useState<Entity[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    api<Entity[]>("/instruments", undefined, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) {
          setInstruments(data);
          setLoading(false);
          setError("");
        }
      },
      (error) => {
        if (!controller.signal.aborted) {
          setError(error.message);
          setLoading(false);
        }
      },
    );
    return () => controller.abort();
  }, [revision]);
  const instrument =
    instruments.find((item) => String(item.id) === selected) ?? instruments[0];
  return (
    <section className="panel">
      <h2>Instrument market prices</h2>
      <p>
        Manual direct unit prices. Zero is valid. One observation per
        Instrument/date. These are not journal transactions.
      </p>
      {loading ? (
        <p role="status">Loading Instruments…</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : !instrument ? (
        <p>
          No Instruments yet. Create an Instrument through Record transaction
          first.
        </p>
      ) : (
        <>
          <label>
            Price Instrument
            <select
              value={instrument.id}
              onChange={(event) => setSelected(event.target.value)}
            >
              {instruments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · #{item.id}
                </option>
              ))}
            </select>
          </label>
          <PriceHistory
            key={instrument.id}
            instrument={instrument}
            onChanged={onChanged}
          />
        </>
      )}
      <button
        className="secondary"
        onClick={() => {
          setLoading(true);
          setRevision((value) => value + 1);
        }}
      >
        Refresh Instruments
      </button>
    </section>
  );
}

function PriceHistory({
  instrument,
  onChanged,
}: {
  instrument: Entity;
  onChanged: () => void;
}) {
  const [state, setState] = useState<{ data?: Observation[]; error?: string }>(
    {},
  );
  const [revision, setRevision] = useState(0);
  const [edit, setEdit] = useState<{
    observation?: Observation;
    deleting?: boolean;
  } | null>(null);
  const path = `/instruments/${instrument.id}/market-prices`;
  useEffect(() => {
    const controller = new AbortController();
    api<Observation[]>(path, undefined, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ data });
      },
      (error) => {
        if (!controller.signal.aborted) setState({ error: error.message });
      },
    );
    return () => controller.abort();
  }, [path, revision]);
  return (
    <>
      <button onClick={() => setEdit({})}>Add market price</button>
      <button
        className="secondary"
        onClick={() => {
          setState({});
          setRevision((value) => value + 1);
        }}
      >
        Refresh prices
      </button>
      {state.error ? (
        <p role="alert" className="error">
          {state.error}
        </p>
      ) : !state.data ? (
        <p role="status">Loading price history…</p>
      ) : !state.data.length ? (
        <p>No market prices recorded.</p>
      ) : (
        state.data.map((item) => (
          <article className="notice" key={item.id}>
            <p>
              {item.effective_date} · {item.price} {item.currency_code}
            </p>
            <button
              className="secondary"
              onClick={() => setEdit({ observation: item })}
            >
              Edit price {item.effective_date}
            </button>
            <button
              className="secondary"
              onClick={() => setEdit({ observation: item, deleting: true })}
            >
              Delete price {item.effective_date}
            </button>
          </article>
        ))
      )}
      {edit && (
        <PriceDialog
          instrument={instrument}
          {...edit}
          onClose={() => setEdit(null)}
          onSaved={() => {
            setEdit(null);
            setState({});
            setRevision((value) => value + 1);
            onChanged();
          }}
        />
      )}
    </>
  );
}

function PriceDialog({
  instrument,
  observation,
  deleting,
  onClose,
  onSaved,
}: {
  instrument: Entity;
  observation?: Observation;
  deleting?: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [price, setPrice] = useState(observation?.price ?? "");
  const [currency, setCurrency] = useState(observation?.currency_code ?? "USD");
  const [date, setDate] = useState(observation?.effective_date ?? localDate());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const units = decimalUnits(price, 12);
  const invalid =
    units === null || units < BigInt(0) || units >= BigInt(10) ** BigInt(28)
      ? "Enter a non-negative exact price with at most 12 decimal places and 16 integer digits."
      : !/^[A-Z]{3}$/.test(currency)
        ? "Use three uppercase currency letters."
        : dateError(date);
  return (
    <Dialog
      title={
        deleting
          ? "Delete market price"
          : observation
            ? "Edit market price"
            : "Add market price"
      }
      busy={busy}
      onClose={onClose}
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (lock.current || (!deleting && invalid)) return;
          lock.current = true;
          setBusy(true);
          setError("");
          controller.current = new AbortController();
          try {
            await api(
              `/instruments/${instrument.id}/market-prices${observation ? `/${observation.id}` : ""}`,
              deleting
                ? undefined
                : {
                    price: normalizeDecimal(price),
                    currency_code: currency,
                    effective_date: date,
                  },
              controller.current.signal,
              deleting ? "DELETE" : observation ? "PUT" : undefined,
            );
            if (!controller.current.signal.aborted) onSaved();
          } catch (error) {
            if (!controller.current.signal.aborted)
              setError(
                error instanceof Error
                  ? error.message
                  : "Price could not be saved.",
              );
          } finally {
            if (!controller.current.signal.aborted) {
              lock.current = false;
              setBusy(false);
            }
          }
        }}
      >
        <p>
          {instrument.name} · #{instrument.id}. Historical valuation is
          recomputed after changes.
        </p>
        {deleting ? (
          <p>
            Delete this observation permanently? An earlier applicable price may
            be selected instead.
          </p>
        ) : (
          <>
            <label>
              Unit market price
              <input
                value={price}
                onChange={(event) => setPrice(event.target.value)}
                inputMode="decimal"
                disabled={busy}
              />
            </label>
            <label>
              Price currency
              <input
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
                disabled={busy}
              />
            </label>
            <label>
              Price effective date
              <input
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
                disabled={busy}
              />
            </label>
            {invalid && <p role="alert">{invalid}</p>}
          </>
        )}
        {error && (
          <p role="alert" className="error">
            {error} Nothing was saved or removed.
          </p>
        )}
        <button disabled={busy || (!deleting && !!invalid)}>
          {busy
            ? "Saving…"
            : deleting
              ? "Confirm delete price"
              : "Save market price"}
        </button>
      </form>
    </Dialog>
  );
}
