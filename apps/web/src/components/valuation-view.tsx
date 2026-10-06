"use client";
import { formatMoney, parseMoney, type MoneyWire } from "../lib/exact-money";
import { dateError } from "./entry-dialogs";

type Price = { price: string; currency_code: string; effective_date: string };
type Unresolved = {
  account_id: number;
  instrument_id: number;
  instrument_name: string;
  quantity: string;
} & (
  | { reason: "MISSING_MARKET_PRICE" }
  | {
      reason: "MISSING_ACQUISITION_BASIS" | "UNSUPPORTED_NEGATIVE_POSITION";
      market_value_component: MoneyWire | null;
    }
  | {
      reason: "CURRENCY_MISMATCH";
      market_value_component: MoneyWire;
      remaining_basis: MoneyWire;
    }
);
export type Valuation = {
  metric: "SECURITY_VALUATION_AND_UNREALISED_PNL";
  as_of_date: string;
  resolved_market_value_by_currency: MoneyWire[];
  resolved_unrealised_pnl_by_currency: MoneyWire[];
  is_fully_resolved: boolean;
  instruments: {
    account_id: number;
    instrument_id: number;
    instrument_name: string;
    quantity: string;
    selected_market_price: Price | null;
    market_value: MoneyWire | null;
    resolved_unrealised_pnl_by_currency: MoneyWire[];
    unresolved_components: Unresolved[];
    is_fully_resolved: boolean;
  }[];
};
const reasons = {
  MISSING_MARKET_PRICE: "Missing market price",
  CURRENCY_MISMATCH: "Currency mismatch — no FX conversion",
  MISSING_ACQUISITION_BASIS: "Missing acquisition basis",
  UNSUPPORTED_NEGATIVE_POSITION:
    "Negative position — short unrealised result unsupported",
};
const money = (value: MoneyWire) => formatMoney(parseMoney(value));

function validValuation(data: Valuation): boolean {
  try {
    if (
      data.metric !== "SECURITY_VALUATION_AND_UNREALISED_PNL" ||
      typeof data.is_fully_resolved !== "boolean"
    )
      return false;
    data.resolved_market_value_by_currency.forEach(money);
    data.resolved_unrealised_pnl_by_currency.forEach(money);
    data.instruments.forEach((item) => {
      if (
        typeof item.is_fully_resolved !== "boolean" ||
        typeof item.quantity !== "string"
      )
        throw new Error("Invalid position");
      if (item.market_value !== null) money(item.market_value);
      item.resolved_unrealised_pnl_by_currency.forEach(money);
      item.unresolved_components.forEach((component) => {
        if (!Object.hasOwn(reasons, component.reason))
          throw new Error("Unknown unresolved reason");
        if (
          component.reason === "CURRENCY_MISMATCH" &&
          (!component.market_value_component || !component.remaining_basis)
        )
          throw new Error("Missing unresolved legs");
        if (
          "market_value_component" in component &&
          component.market_value_component !== null
        )
          money(component.market_value_component);
        if ("remaining_basis" in component) money(component.remaining_basis);
      });
    });
    return true;
  } catch {
    return false;
  }
}

export function ValuationView({
  data,
  asOf,
  setAsOf,
}: {
  data?: Valuation;
  asOf: string;
  setAsOf: (date: string) => void;
}) {
  let content;
  if (data && validValuation(data)) {
    content = (
      <>
        <p className={data.is_fully_resolved ? "notice" : "error"}>
          {data.is_fully_resolved
            ? "Fully resolved"
            : "Incomplete — resolved subtotals are not complete totals."}
        </p>
        <h3>Resolved security market value</h3>
        {data.resolved_market_value_by_currency.map((value) => (
          <p key={value.currency_code}>{money(value)}</p>
        ))}
        <h3>Resolved unrealised result</h3>
        {data.resolved_unrealised_pnl_by_currency.map((value) => (
          <p key={value.currency_code}>{money(value)}</p>
        ))}
        {!data.instruments.length && (
          <p>
            No open security positions as of this date. No market price is
            required.
          </p>
        )}
        {data.instruments.map((item, index) => (
          <section className="notice" key={`${item.instrument_id}-${index}`}>
            <h3>
              {item.instrument_name} · #{item.instrument_id}
            </h3>
            <p>Account #{item.account_id} contribution</p>
            <p>Quantity: {item.quantity}</p>
            <p>
              {item.selected_market_price
                ? `Selected price: ${item.selected_market_price.price} ${item.selected_market_price.currency_code} · ${item.selected_market_price.effective_date}`
                : "No applicable market price"}
            </p>
            <p>
              Market value:{" "}
              {item.market_value === null
                ? "Unresolved"
                : money(item.market_value)}
            </p>
            {item.resolved_unrealised_pnl_by_currency.map((value) => (
              <p key={value.currency_code}>Unrealised result: {money(value)}</p>
            ))}
            {item.unresolved_components.map((component, i) => {
              if (!(component.reason in reasons))
                throw new Error("Unknown unresolved reason");
              if (
                component.reason === "CURRENCY_MISMATCH" &&
                (!component.market_value_component ||
                  !component.remaining_basis)
              )
                throw new Error("Missing unresolved legs");
              return (
                <div className="error" key={i}>
                  <p>
                    {reasons[component.reason]} · Account #
                    {component.account_id} · Quantity {component.quantity}
                  </p>
                  {"market_value_component" in component &&
                    component.market_value_component !== null && (
                      <p>
                        Marked value: {money(component.market_value_component)}
                      </p>
                    )}
                  {"remaining_basis" in component && (
                    <p>Remaining basis: {money(component.remaining_basis)}</p>
                  )}
                </div>
              );
            })}
          </section>
        ))}
      </>
    );
  } else if (data) {
    content = (
      <p className="error" role="alert">
        Invalid valuation response. No guessed financial values have been
        rendered. Refresh to retry.
      </p>
    );
  }
  return (
    <>
      <label>
        Valuation as-of date
        <input
          type="date"
          value={asOf}
          onChange={(event) => setAsOf(event.target.value)}
        />
      </label>
      {dateError(asOf) && <p role="alert">{dateError(asOf)}</p>}
      <p>
        Security valuation only — excludes cash, income and realised result.
        Currencies remain separate. ≈ marks display-only approximation.
      </p>
      {content}
    </>
  );
}
