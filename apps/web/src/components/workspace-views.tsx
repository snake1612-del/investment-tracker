import type { Entity, Position, Realised, Transaction } from "../lib/api";
import { decimalUnits, formatMoney, parseMoney } from "../lib/exact-money";

export function Holdings({
  positions,
  account,
}: {
  positions: Position[];
  account: boolean;
}) {
  if (!positions.length)
    return (
      <div className="empty">
        <h3>No holdings yet</h3>
        <p>
          Recorded buys and sells will reconstruct instrument quantities here.
        </p>
      </div>
    );
  return (
    <>
      <table>
        <thead>
          <tr>
            <th>Instrument</th>
            <th className="numeric">Quantity</th>
            {account && <th>Status</th>}
          </tr>
        </thead>
        <tbody>
          {positions.map((position) => (
            <tr key={position.instrument_id}>
              <td>
                {position.instrument_name}
                <small>Instrument #{position.instrument_id}</small>
              </td>
              <td className="numeric">
                {position.quantity.replace(/^-/, "−")}
              </td>
              {account && (
                <td>
                  {decimalUnits(position.quantity) !== null &&
                  decimalUnits(position.quantity)! < BigInt(0)
                    ? "Negative quantity"
                    : decimalUnits(position.quantity) === BigInt(0)
                      ? "Zero quantity"
                      : "Held"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {positions.some((p) => p.quantity.startsWith("-")) && (
        <p className="notice">
          Negative quantity: recorded history currently reconstructs a negative
          position. This is not a technical error.
        </p>
      )}
    </>
  );
}

export function History({
  transactions,
  instruments,
}: {
  transactions: Transaction[];
  instruments: Entity[];
}) {
  if (!transactions.length)
    return (
      <div className="empty">
        <h3>No transactions yet</h3>
        <p>Record your first deposit, buy or sell.</p>
      </div>
    );
  const ordered = [...transactions].sort(
    (a, b) => b.effective_date.localeCompare(a.effective_date) || b.id - a.id,
  );
  const name = (id: number | null) =>
    id === null
      ? "—"
      : `${instruments.find((i) => i.id === id)?.name ?? "Instrument"} · #${id}`;
  return (
    <>
      <table className="history-table">
        <thead>
          <tr>
            {[
              "Effective date",
              "Type",
              "Instrument",
              "Quantity",
              "Price",
              "Cash amount",
              "Currency",
            ].map((label) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordered.map((t) => (
            <tr key={t.id} id={`transaction-${t.id}`}>
              <td>
                {t.effective_date}
                <small>Transaction #{t.id}</small>
              </td>
              <td>{t.type}</td>
              <td>{name(t.instrument_id)}</td>
              <td>{t.quantity ?? "—"}</td>
              <td>{t.price ?? "—"}</td>
              <td>{t.cash_amount}</td>
              <td>{t.currency_code}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="history-mobile">
        {ordered.map((t) => (
          <article key={t.id}>
            <header>
              <strong>{t.type}</strong>
              <span>{t.effective_date}</span>
            </header>
            <p>{name(t.instrument_id)}</p>
            <dl>
              <dt>Quantity</dt>
              <dd>{t.quantity ?? "—"}</dd>
              <dt>Price</dt>
              <dd>{t.price ?? "—"}</dd>
              <dt>Cash amount</dt>
              <dd>
                {t.cash_amount} {t.currency_code}
              </dd>
            </dl>
            <small>Transaction #{t.id}</small>
          </article>
        ))}
      </div>
    </>
  );
}

export function RealisedResult({ result }: { result: Realised }) {
  let payloadError = "";
  let amounts: ReturnType<typeof parseMoney>[] = [];
  try {
    if (
      result.metric !== "GROSS_TRADE_CASH_REALISED_PNL" ||
      !Array.isArray(result.resolved_pnl_by_currency) ||
      !Array.isArray(result.unresolved_components) ||
      typeof result.is_fully_resolved !== "boolean" ||
      result.is_fully_resolved !== (result.unresolved_components.length === 0)
    )
      throw new Error("Invalid realised result payload.");
    amounts = result.resolved_pnl_by_currency.map(parseMoney);
    if (new Set(amounts.map((m) => m.currency)).size !== amounts.length)
      throw new Error("Invalid duplicate currency subtotals.");
    for (const u of result.unresolved_components) {
      parseMoney(u.allocated_proceeds);
      if (u.reason === "CURRENCY_MISMATCH") {
        if (!u.removed_basis)
          throw new Error("Invalid currency mismatch payload.");
        parseMoney(u.removed_basis);
      } else if (u.reason !== "MISSING_ACQUISITION_BASIS")
        throw new Error("Unknown unresolved reason.");
    }
  } catch (error) {
    payloadError =
      error instanceof Error ? error.message : "Invalid financial payload.";
  }
  if (payloadError)
    return (
      <p role="alert" className="error">
        {payloadError} Unable to display financial results.
      </p>
    );
  return (
    <section>
      <div className="result-heading">
        <h3>Realised trading result</h3>
        <span className="badge">Gross</span>
        <span className={`badge ${result.is_fully_resolved ? "" : "warning"}`}>
          {result.is_fully_resolved ? "Resolved" : "Incomplete"}
        </span>
      </div>
      <p>Before fees, taxes and FX conversion.</p>
      <p className="muted">
        Matched acquisition basis and SELL cash proceeds. Not total portfolio
        return or net profit.
      </p>
      {!amounts.length && !result.unresolved_components.length ? (
        <div className="empty">No realised activity yet</div>
      ) : (
        <div className="currency-results">
          {amounts.map((money) => (
            <div key={money.currency} className="currency-result">
              <small>
                {money.currency}
                {!result.is_fully_resolved && " · resolved subtotal only"}
              </small>
              <strong
                title={`Exact value: ${money.numerator} / ${money.denominator} ${money.currency}`}
              >
                {formatMoney(money)}
              </strong>
            </div>
          ))}
        </div>
      )}
      {result.unresolved_components.length > 0 && (
        <>
          <h4>Unresolved activity</h4>
          {result.unresolved_components.map((u, index) => (
            <article
              className="unresolved"
              key={`${u.account_id}-${u.sell_transaction_id}-${index}`}
            >
              <strong>
                {u.reason === "CURRENCY_MISMATCH"
                  ? "Currency mismatch"
                  : "Missing acquisition basis"}
              </strong>
              <p>
                {u.reason === "CURRENCY_MISMATCH"
                  ? "Acquisition basis and sell proceeds use different currencies; no FX conversion is applied."
                  : "Part of this SELL has no matching acquisition basis in recorded history."}
              </p>
              <p>
                {u.instrument_name} · Instrument #{u.instrument_id} ·{" "}
                {u.effective_date} · Quantity {u.quantity}
              </p>
              <small>
                Account #{u.account_id} · SELL transaction #
                {u.sell_transaction_id}
              </small>
              <details>
                <summary>Details</summary>
                <p>
                  Allocated proceeds:{" "}
                  {formatMoney(parseMoney(u.allocated_proceeds))}
                </p>
                {u.removed_basis && (
                  <p>
                    Removed basis: {formatMoney(parseMoney(u.removed_basis))}
                  </p>
                )}
              </details>
            </article>
          ))}
        </>
      )}
    </section>
  );
}
