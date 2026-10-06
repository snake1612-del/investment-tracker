import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceView, type Performance } from "./performance-view";

const exact = (numerator: string, denominator = "1") => ({
  currency_code: "USD",
  amount: { numerator, denominator },
});
const ratio = (numerator: string, denominator = "1") => ({
  numerator,
  denominator,
});
function resolved(): Performance {
  return {
    start_date: "2020-01-02",
    end_date: "2020-01-03",
    performance: {
      currency_code: "USD",
      opening_value: exact("100"),
      closing_value: exact("110"),
      twr: ratio("1", "10"),
      unresolved_components: [],
      is_fully_resolved: true,
    },
    benchmark: {
      instrument_id: 2,
      instrument_name: "Reference",
      currency_code: "USD",
      opening_value: exact("100"),
      ending_value: exact("120"),
      benchmark_twr: ratio("1", "5"),
      active_return: ratio("-1", "10"),
      ending_value_difference: exact("-10"),
      unresolved_components: [],
      is_fully_resolved: true,
    },
  };
}
const controls = {
  start: "2020-01-02",
  end: "2020-01-03",
  benchmark: "2",
  setStart: vi.fn(),
  setEnd: vi.fn(),
  setBenchmark: vi.fn(),
  instruments: [{ id: 2, name: "Reference" }],
};

describe("Portfolio Performance presentation", () => {
  it("formats only exact API outputs, not browser-calculated returns", () => {
    render(<PerformanceView {...controls} data={resolved()} />);
    expect(screen.getByText("Portfolio TWR: 10%")).toBeInTheDocument();
    expect(screen.getByText("Benchmark TWR: 20%")).toBeInTheDocument();
    expect(screen.getByText("Active return: −10%")).toBeInTheDocument();
    expect(
      screen.getByText("Ending-value difference: −10 USD"),
    ).toBeInTheDocument();
  });
  it("preserves exact zero and absent optional benchmark", () => {
    const data = resolved();
    data.performance.twr = ratio("0");
    data.benchmark = null;
    render(<PerformanceView {...controls} data={data} />);
    expect(screen.getByText("Portfolio TWR: 0%")).toBeInTheDocument();
    expect(screen.queryByText(/Benchmark TWR:/)).not.toBeInTheDocument();
  });
  it("shows missing price diagnostics and never guessed zero", () => {
    const data = resolved();
    data.benchmark = null;
    data.performance = {
      currency_code: "USD",
      opening_value: exact("100"),
      closing_value: null,
      twr: null,
      is_fully_resolved: false,
      unresolved_components: [
        {
          reason: "MISSING_MARKET_PRICE",
          date: "2020-01-03",
          account_id: 7,
          instrument_id: 9,
          instrument_name: "Missing quote",
          currencies: [],
          value: null,
          capital_base: null,
        },
      ],
    };
    render(<PerformanceView {...controls} data={data} />);
    expect(screen.getByText("Portfolio TWR: Unresolved")).toBeInTheDocument();
    expect(
      screen.getByText("Closing Performance Value: Unresolved"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Missing market price · 2020-01-03"),
    ).toBeInTheDocument();
    expect(screen.getByText("Account #7")).toBeInTheDocument();
    expect(screen.getByText("Missing quote · #9")).toBeInTheDocument();
  });
  it("shows zero-base benchmark recovery separately from resolved Portfolio", () => {
    const data = resolved();
    data.benchmark = {
      ...data.benchmark!,
      benchmark_twr: null,
      active_return: null,
      ending_value_difference: null,
      is_fully_resolved: false,
      unresolved_components: [
        {
          reason: "ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE",
          date: "2020-01-03",
          account_id: null,
          instrument_id: 2,
          instrument_name: "Reference",
          currencies: [],
          value: exact("100"),
          capital_base: exact("0"),
        },
      ],
    };
    render(<PerformanceView {...controls} data={data} />);
    expect(screen.getByText("Portfolio TWR: 10%")).toBeInTheDocument();
    expect(screen.getByText("Benchmark TWR: Unresolved")).toBeInTheDocument();
    expect(
      screen.getByText(
        /Zero adjusted capital base with positive closing value/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Adjusted capital base: 0 USD"),
    ).toBeInTheDocument();
  });
  it("shows negative opening value without mislabelling it as closing value", () => {
    const data = resolved();
    data.benchmark = null;
    data.performance.opening_value = exact("-100");
    data.performance.closing_value = exact("100");
    data.performance.twr = null;
    data.performance.is_fully_resolved = false;
    data.performance.unresolved_components = [
      {
        reason: "NEGATIVE_PERFORMANCE_VALUE",
        date: "2020-01-01",
        account_id: null,
        instrument_id: null,
        instrument_name: null,
        currencies: [],
        value: exact("-100"),
        capital_base: null,
      },
    ];
    render(<PerformanceView {...controls} data={data} />);
    expect(screen.getByText("Portfolio TWR: Unresolved")).toBeInTheDocument();
    expect(screen.getByText("Value: −100 USD")).toBeInTheDocument();
    expect(
      screen.getByText("Closing Performance Value: 100 USD"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Closing value:/)).not.toBeInTheDocument();
  });
  it.each([
    ratio("1", "0"),
    ratio("2", "4"),
    ratio("0", "2"),
    ratio("01"),
    ratio("1", "-2"),
  ])("fails safely for malformed exact ratios %o", (twr) => {
    const data = resolved();
    data.performance.twr = twr;
    render(<PerformanceView {...controls} data={data} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "No guessed financial values",
    );
    expect(screen.queryByText(/Portfolio TWR:/)).not.toBeInTheDocument();
  });
  it("does not display a partial unresolved return", () => {
    const data = resolved();
    data.performance.is_fully_resolved = false;
    render(<PerformanceView {...controls} data={data} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Invalid performance response",
    );
  });
  it("passes request-scoped period and optional benchmark controls", () => {
    render(<PerformanceView {...controls} />);
    fireEvent.change(screen.getByLabelText("Performance start date"), {
      target: { value: "2020-01-01" },
    });
    fireEvent.change(screen.getByLabelText("Performance end date"), {
      target: { value: "2020-01-04" },
    });
    fireEvent.change(screen.getByLabelText("Benchmark Instrument"), {
      target: { value: "" },
    });
    expect(controls.setStart).toHaveBeenCalledWith("2020-01-01");
    expect(controls.setEnd).toHaveBeenCalledWith("2020-01-04");
    expect(controls.setBenchmark).toHaveBeenCalledWith("");
  });
  it("validates period ordering before requesting", () => {
    render(<PerformanceView {...controls} start="2020-01-04" />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Start date must not be after end date",
    );
  });
});
