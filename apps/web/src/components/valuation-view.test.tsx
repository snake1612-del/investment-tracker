import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ValuationView, type Valuation } from "./valuation-view";
const usd = {
  currency_code: "USD",
  amount: { numerator: "30", denominator: "1" },
};
function value(): Valuation {
  return {
    metric: "SECURITY_VALUATION_AND_UNREALISED_PNL",
    as_of_date: "2020-01-02",
    resolved_market_value_by_currency: [usd],
    resolved_unrealised_pnl_by_currency: [usd],
    is_fully_resolved: true,
    instruments: [
      {
        account_id: 1,
        instrument_id: 1,
        instrument_name: "Fund",
        quantity: "2",
        selected_market_price: {
          price: "15",
          currency_code: "USD",
          effective_date: "2020-01-01",
        },
        market_value: usd,
        resolved_unrealised_pnl_by_currency: [usd],
        unresolved_components: [],
        is_fully_resolved: true,
      },
    ],
  };
}
describe("F009 presentation", () => {
  it("renders exact API results and selected price provenance", () => {
    render(
      <ValuationView data={value()} asOf="2020-01-02" setAsOf={vi.fn()} />,
    );
    expect(screen.getByText("Fully resolved")).toBeInTheDocument();
    expect(screen.getByText("Market value: 30 USD")).toBeInTheDocument();
    expect(
      screen.getByText(/Selected price: 15 USD · 2020-01-01/),
    ).toBeInTheDocument();
  });
  it("preserves missing values and incomplete subtotals", () => {
    const data = value();
    data.is_fully_resolved = false;
    data.instruments[0] = {
      ...data.instruments[0],
      selected_market_price: null,
      market_value: null,
      resolved_unrealised_pnl_by_currency: [],
      is_fully_resolved: false,
      unresolved_components: [
        {
          account_id: 2,
          instrument_id: 1,
          instrument_name: "Fund",
          quantity: "2",
          reason: "MISSING_MARKET_PRICE",
        },
      ],
    };
    render(<ValuationView data={data} asOf="2020-01-02" setAsOf={vi.fn()} />);
    expect(screen.getByText("Market value: Unresolved")).toBeInTheDocument();
    expect(
      screen.getByText(/Incomplete — resolved subtotals/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Missing market price · Account #2/),
    ).toBeInTheDocument();
  });
  it("fails safely for malformed money without guessed zero", () => {
    const data = value();
    data.resolved_market_value_by_currency[0] = {
      ...usd,
      amount: { numerator: "0", denominator: "0" },
    };
    render(<ValuationView data={data} asOf="2020-01-02" setAsOf={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "No guessed financial values",
    );
    expect(screen.queryByText("Market value: 30 USD")).not.toBeInTheDocument();
  });
  it("as-of controls pass explicit dates without financial calculations", () => {
    const change = vi.fn();
    render(<ValuationView asOf="2020-01-02" setAsOf={change} />);
    fireEvent.change(screen.getByLabelText("Valuation as-of date"), {
      target: { value: "2020-01-01" },
    });
    expect(change).toHaveBeenCalledWith("2020-01-01");
  });
});
