"use client";

import type { Entity } from "../lib/api";
import {
  formatMoney,
  formatPercent,
  parseMoney,
  parseRatio,
  type MoneyWire,
  type RatioWire,
} from "../lib/exact-money";
import { dateError } from "./entry-dialogs";

type PerformanceReason =
  | "MISSING_MARKET_PRICE"
  | "MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX"
  | "NON_POSITIVE_CAPITAL_BASE"
  | "ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE"
  | "NEGATIVE_PERFORMANCE_VALUE"
  | "NO_CAPITAL_AT_RISK";
type BenchmarkReason =
  | "UNRESOLVED_PORTFOLIO_PERFORMANCE"
  | "MISSING_BENCHMARK_MARKET_PRICE"
  | "BENCHMARK_CURRENCY_MISMATCH"
  | "ZERO_BENCHMARK_OPENING_PRICE"
  | "ZERO_BENCHMARK_FLOW_EXECUTION_PRICE"
  | "BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE"
  | "ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE";
type Diagnostic<R> = {
  reason: R;
  date: string | null;
  account_id: number | null;
  instrument_id: number | null;
  instrument_name: string | null;
  currencies: string[];
  value: MoneyWire | null;
  capital_base: MoneyWire | null;
};
type Result<R> = {
  currency_code: string | null;
  opening_value: MoneyWire | null;
  unresolved_components: Diagnostic<R>[];
  is_fully_resolved: boolean;
};
export type Performance = {
  start_date: string;
  end_date: string;
  performance: Result<PerformanceReason> & {
    closing_value: MoneyWire | null;
    twr: RatioWire | null;
  };
  benchmark:
    | (Result<BenchmarkReason> & {
        instrument_id: number;
        instrument_name: string;
        ending_value: MoneyWire | null;
        benchmark_twr: RatioWire | null;
        active_return: RatioWire | null;
        ending_value_difference: MoneyWire | null;
      })
    | null;
};

const reasons = {
  MISSING_MARKET_PRICE: "Missing market price",
  MULTI_CURRENCY_PERFORMANCE_REQUIRES_FX:
    "Multi-currency performance requires FX — no conversion available",
  NON_POSITIVE_CAPITAL_BASE: "Negative adjusted capital base",
  ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE:
    "Zero adjusted capital base with positive closing value",
  NEGATIVE_PERFORMANCE_VALUE: "Negative Performance Value",
  NO_CAPITAL_AT_RISK: "No capital at risk — not a zero return",
  UNRESOLVED_PORTFOLIO_PERFORMANCE: "Portfolio performance is unresolved",
  MISSING_BENCHMARK_MARKET_PRICE: "Missing benchmark market price",
  BENCHMARK_CURRENCY_MISMATCH: "Benchmark currency mismatch — no FX conversion",
  ZERO_BENCHMARK_OPENING_PRICE:
    "Zero benchmark opening price — cannot create units",
  ZERO_BENCHMARK_FLOW_EXECUTION_PRICE: "Zero benchmark flow-execution price",
  BENCHMARK_WITHDRAWAL_EXCEEDS_VALUE:
    "Withdrawal exceeds benchmark value — no benchmark shorting",
};
const money = (value: MoneyWire | null) =>
  value === null ? "Unresolved" : formatMoney(parseMoney(value));
const percent = (value: RatioWire | null) =>
  value === null ? "Unresolved" : formatPercent(value);

export function periodError(start: string, end: string): string | undefined {
  return (
    dateError(start) ??
    dateError(end) ??
    (start === "0001-01-01"
      ? "An opening date before the period is required."
      : start > end
        ? "Start date must not be after end date."
        : undefined)
  );
}

function valid(data: Performance): boolean {
  try {
    if (periodError(data.start_date, data.end_date)) return false;
    const p = data.performance;
    money(p.opening_value);
    money(p.closing_value);
    if (p.twr !== null) parseRatio(p.twr);
    const b = data.benchmark;
    if (b) {
      money(b.opening_value);
      money(b.ending_value);
      money(b.ending_value_difference);
      for (const value of [b.benchmark_twr, b.active_return])
        if (value !== null) parseRatio(value);
      if (
        b.is_fully_resolved &&
        (!p.is_fully_resolved ||
          b.benchmark_twr === null ||
          b.active_return === null ||
          b.ending_value_difference === null)
      )
        return false;
      if (
        !b.is_fully_resolved &&
        (b.benchmark_twr !== null ||
          b.active_return !== null ||
          b.ending_value_difference !== null)
      )
        return false;
    }
    for (const result of b ? [p, b] : [p]) {
      if (
        typeof result.is_fully_resolved !== "boolean" ||
        result.is_fully_resolved !== (result.unresolved_components.length === 0)
      )
        return false;
      for (const diagnostic of result.unresolved_components) {
        if (
          !Object.hasOwn(reasons, diagnostic.reason) ||
          !Array.isArray(diagnostic.currencies)
        )
          return false;
        money(diagnostic.value);
        money(diagnostic.capital_base);
      }
    }
    return p.is_fully_resolved
      ? p.twr !== null && p.opening_value !== null && p.closing_value !== null
      : p.twr === null;
  } catch {
    return false;
  }
}

function Diagnostics({
  items,
}: {
  items: Diagnostic<PerformanceReason | BenchmarkReason>[];
}) {
  return items.map((item, index) => (
    <section className="error" key={index}>
      <p>
        {reasons[item.reason]}
        {item.date ? ` · ${item.date}` : ""}
      </p>
      {item.account_id !== null && <p>Account #{item.account_id}</p>}
      {item.instrument_id !== null && (
        <p>
          {item.instrument_name} · #{item.instrument_id}
        </p>
      )}
      {!!item.currencies.length && (
        <p>Currencies: {item.currencies.join(", ")}</p>
      )}
      {item.value !== null && <p>Value: {money(item.value)}</p>}
      {item.capital_base !== null && (
        <p>Adjusted capital base: {money(item.capital_base)}</p>
      )}
    </section>
  ));
}

export function PerformanceView({
  data,
  start,
  end,
  benchmark,
  setStart,
  setEnd,
  setBenchmark,
  instruments,
}: {
  data?: Performance;
  start: string;
  end: string;
  benchmark: string;
  setStart: (value: string) => void;
  setEnd: (value: string) => void;
  setBenchmark: (value: string) => void;
  instruments: Entity[];
}) {
  return (
    <>
      <div className="context">
        <label>
          Performance start date
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          Performance end date
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label>
          Benchmark Instrument
          <select
            value={benchmark}
            onChange={(e) => setBenchmark(e.target.value)}
          >
            <option value="">No benchmark</option>
            {instruments.map((instrument) => (
              <option key={instrument.id} value={instrument.id}>
                {instrument.name} · #{instrument.id}
              </option>
            ))}
          </select>
        </label>
      </div>
      {periodError(start, end) && (
        <p role="alert" className="error">
          {periodError(start, end)}
        </p>
      )}
      <p>
        Portfolio cash + signed security market value. TWR neutralizes net
        start-of-day deposits/withdrawals; recorded fees and taxes reduce
        returns. Benchmark is price-only. No FX. ≈ marks display-only
        approximation.
      </p>
      {data &&
        (valid(data) ? (
          <>
            <h3>Portfolio TWR: {percent(data.performance.twr)}</h3>
            <p>
              Opening Performance Value: {money(data.performance.opening_value)}
            </p>
            <p>
              Closing Performance Value: {money(data.performance.closing_value)}
            </p>
            <Diagnostics items={data.performance.unresolved_components} />
            {data.benchmark && (
              <section className="notice">
                <h3>Benchmark: {data.benchmark.instrument_name}</h3>
                <p>Benchmark TWR: {percent(data.benchmark.benchmark_twr)}</p>
                <p>Active return: {percent(data.benchmark.active_return)}</p>
                <p>
                  Benchmark opening value: {money(data.benchmark.opening_value)}
                </p>
                <p>
                  Benchmark ending value: {money(data.benchmark.ending_value)}
                </p>
                <p>
                  Ending-value difference:{" "}
                  {money(data.benchmark.ending_value_difference)}
                </p>
                <Diagnostics items={data.benchmark.unresolved_components} />
              </section>
            )}
          </>
        ) : (
          <p role="alert" className="error">
            Invalid performance response. No guessed financial values have been
            rendered. Refresh to retry.
          </p>
        ))}
    </>
  );
}
