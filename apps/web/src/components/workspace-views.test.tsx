import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Realised, Transaction } from "../lib/api";
import { Holdings, History, RealisedResult } from "./workspace-views";

const empty: Realised = {
  metric: "GROSS_TRADE_CASH_REALISED_PNL",
  resolved_pnl_by_currency: [],
  unresolved_components: [],
  is_fully_resolved: true,
};
describe("workspace financial views", () => {
  it("distinguishes no activity from exact zero", () => {
    const { rerender } = render(<RealisedResult result={empty} />);
    expect(screen.getByText("No realised activity yet")).toBeInTheDocument();
    rerender(
      <RealisedResult
        result={{
          ...empty,
          resolved_pnl_by_currency: [
            {
              currency_code: "USD",
              amount: { numerator: "0", denominator: "1" },
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("0 USD")).toBeInTheDocument();
    expect(
      screen.queryByText("No realised activity yet"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Gross")).toBeInTheDocument();
    expect(screen.getByText("Resolved")).toBeInTheDocument();
  });
  it("keeps multiple currencies and negative values explicit", () => {
    render(
      <RealisedResult
        result={{
          ...empty,
          resolved_pnl_by_currency: [
            {
              currency_code: "EUR",
              amount: { numerator: "-25", denominator: "2" },
            },
            {
              currency_code: "USD",
              amount: { numerator: "100", denominator: "3" },
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("−12.5 EUR")).toBeInTheDocument();
    expect(screen.getByText("≈33.33333333 USD")).toBeInTheDocument();
    expect(
      screen.getByText("Before fees, taxes and FX conversion."),
    ).toBeInTheDocument();
  });
  it.each(["CURRENCY_MISMATCH", "MISSING_ACQUISITION_BASIS"] as const)(
    "shows %s as incomplete, not error",
    (reason) => {
      const money = {
        currency_code: "USD",
        amount: { numerator: "12", denominator: "1" },
      };
      render(
        <RealisedResult
          result={{
            ...empty,
            is_fully_resolved: false,
            resolved_pnl_by_currency: [money],
            unresolved_components: [
              {
                reason,
                account_id: 1,
                sell_transaction_id: 3,
                instrument_id: 2,
                instrument_name: "Fund",
                quantity: "1",
                effective_date: "2026-01-02",
                allocated_proceeds: money,
                ...(reason === "CURRENCY_MISMATCH"
                  ? { removed_basis: { ...money, currency_code: "EUR" } }
                  : {}),
              },
            ],
          }}
        />,
      );
      expect(screen.getByText("Incomplete")).toBeInTheDocument();
      expect(
        screen.getByText("USD · resolved subtotal only"),
      ).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.getByText(/SELL transaction #3/)).toBeInTheDocument();
    },
  );
  it("does not replace malformed exact money with zero", () => {
    render(
      <RealisedResult
        result={{
          ...empty,
          resolved_pnl_by_currency: [
            {
              currency_code: "USD",
              amount: { numerator: "1", denominator: "0" },
            },
          ],
        }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid");
    expect(screen.queryByText("0 USD")).not.toBeInTheDocument();
  });
  it("represents zero and negative holdings honestly", () => {
    render(
      <Holdings
        account
        positions={[
          { instrument_id: 1, instrument_name: "Zero", quantity: "0" },
          { instrument_id: 2, instrument_name: "Short", quantity: "-2.5" },
        ]}
      />,
    );
    expect(screen.getByText("Zero quantity")).toBeInTheDocument();
    expect(screen.getByText("Negative quantity")).toBeInTheDocument();
    expect(screen.getByText("−2.5")).toBeInTheDocument();
  });
  it("sorts history by date then ID, leaving factual values unchanged", () => {
    const base: Transaction = {
      id: 1,
      account_id: 1,
      instrument_id: null,
      type: "DEPOSIT",
      effective_date: "2026-01-01",
      currency_code: "USD",
      quantity: null,
      price: null,
      cash_amount: "100",
    };
    render(
      <History
        instruments={[{ id: 4, name: "Fund" }]}
        transactions={[
          base,
          {
            ...base,
            id: 3,
            type: "BUY",
            instrument_id: 4,
            effective_date: "2026-01-02",
            quantity: "2",
            price: "5",
            cash_amount: "99",
          },
          { ...base, id: 2, effective_date: "2026-01-02" },
        ]}
      />,
    );
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Transaction #3");
    expect(rows[1]).toHaveTextContent("99");
    expect(rows[2]).toHaveTextContent("Transaction #2");
    expect(rows[3]).toHaveTextContent("—");
  });
});
