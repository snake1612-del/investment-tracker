import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TransactionDialog } from "./entry-dialogs";
import { CorrectionDialog } from "./correction-dialog";
import { MoneyView, formatCash, type MoneySummary } from "./money-view";
import { History } from "./workspace-views";
import type { Transaction } from "../lib/api";

const instruments = [
  { id: 2, name: "Fund" },
  { id: 3, name: "Other" },
];
const parent: Transaction = {
  id: 7,
  account_id: 1,
  instrument_id: 2,
  related_transaction_id: null,
  type: "DIVIDEND",
  effective_date: "2020-01-01",
  settlement_date: null,
  currency_code: "USD",
  quantity: null,
  price: null,
  cash_amount: "9007199254740993.12345678",
};
const props = {
  accountId: 1,
  instruments,
  positions: [],
  history: [parent],
  onClose: vi.fn(),
  onRecorded: vi.fn(),
  onInstrumentCreated: vi.fn(),
};
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => vi.unstubAllGlobals());

it.each(["WITHDRAWAL", "DIVIDEND", "COUPON", "FEE", "TAX"])(
  "records strong %s payload without hidden trade fields",
  async (type) => {
    const fetch = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetch);
    render(<TransactionDialog {...props} />);
    fireEvent.change(screen.getByLabelText("Transaction type"), {
      target: { value: type },
    });
    const income = type === "DIVIDEND" || type === "COUPON";
    const charge = type === "FEE" || type === "TAX";
    if (income) {
      expect(
        screen.getByText(/If you only know the net amount/),
      ).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText("Instrument"), {
        target: { value: "2" },
      });
    }
    if (charge)
      expect(screen.getByLabelText("Instrument (optional)")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Currency"), {
      target: { value: "eur" },
    });
    fireEvent.change(
      screen.getByLabelText(income ? "Gross amount" : "Cash amount"),
      { target: { value: "9007199254740993,12345678" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Record transaction" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const payload = JSON.parse(fetch.mock.calls[0][1].body);
    expect(payload.cash_amount).toBe(parent.cash_amount);
    expect(payload.currency_code).toBe("EUR");
    for (const field of ["quantity", "price", "settlement_date", "note"])
      expect(payload).not.toHaveProperty(field);
    if (income) expect(payload.instrument_id).toBe(2);
    if (charge)
      expect(payload).toMatchObject({
        instrument_id: null,
        related_transaction_id: null,
      });
  },
);

it("filters labelled relation candidates, never infers Instrument and blocks explicit mismatch", async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({}));
  vi.stubGlobal("fetch", fetch);
  render(
    <TransactionDialog
      {...props}
      history={[parent, { ...parent, id: 8, type: "FEE" }]}
    />,
  );
  fireEvent.change(screen.getByLabelText("Transaction type"), {
    target: { value: "TAX" },
  });
  fireEvent.change(screen.getByLabelText("Search related transactions"), {
    target: { value: "Fund" },
  });
  const picker = screen.getByLabelText("Related transaction (optional)");
  expect(within(picker).getAllByRole("option")).toHaveLength(2);
  expect(picker).toHaveTextContent(/Dividend · 2020-01-01 · Fund #2/);
  fireEvent.change(picker, { target: { value: "7" } });
  expect(screen.getByLabelText("Instrument (optional)")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Instrument (optional)"), {
    target: { value: "3" },
  });
  fireEvent.change(screen.getByLabelText("Currency"), {
    target: { value: "EUR" },
  });
  fireEvent.change(screen.getByLabelText("Cash amount"), {
    target: { value: "1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Record transaction" }));
  expect(screen.getByText(/Instrument must match/)).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Instrument (optional)"), {
    target: { value: "" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Record transaction" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
    instrument_id: null,
    related_transaction_id: 7,
    currency_code: "EUR",
  });
});

it.each(["WITHDRAWAL", "DIVIDEND", "COUPON", "FEE", "TAX"])(
  "corrects %s with exact prefill and explicit nullable charge replacement",
  async (type) => {
    const fetch = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetch);
    render(
      <CorrectionDialog
        transaction={{
          ...parent,
          id: 9,
          type,
          related_transaction_id: type === "FEE" || type === "TAX" ? 7 : null,
        }}
        history={[parent]}
        instruments={instruments}
        deleting={false}
        onClose={vi.fn()}
        onCorrected={vi.fn()}
      />,
    );
    expect(
      screen.getByLabelText(
        type === "DIVIDEND" || type === "COUPON"
          ? "Gross amount"
          : "Cash amount",
      ),
    ).toHaveValue(parent.cash_amount);
    if (type === "FEE" || type === "TAX") {
      fireEvent.change(screen.getByLabelText("Instrument (optional)"), {
        target: { value: "" },
      });
      fireEvent.change(
        screen.getByLabelText("Related transaction (optional)"),
        { target: { value: "" } },
      );
    }
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const payload = JSON.parse(fetch.mock.calls[0][1].body);
    expect(payload.cash_amount).toBe(parent.cash_amount);
    expect(fetch.mock.calls[0][1].method).toBe("PUT");
    if (type === "FEE" || type === "TAX")
      expect(payload).toMatchObject({
        instrument_id: null,
        related_transaction_id: null,
      });
  },
);

const bucket = {
  currency_code: "USD",
  cash_balance: "-9007199254740993.12345678",
  deposits: "0",
  withdrawals: "0",
  buy_trade_cash_outflow: "0",
  sell_trade_cash_inflow: "0",
  gross_dividend_income: "100",
  gross_coupon_income: "0",
  gross_investment_income: "100",
  fees_paid: "0",
  taxes_paid_or_withheld: "13",
};
const summary: MoneySummary = {
  as_of_date: "2020-01-01",
  currencies: [bucket],
};
it("charge creation locks duplicate submissions and aborts stale-context callbacks", async () => {
  let finish!: (response: Response) => void;
  let signal!: AbortSignal;
  const recorded = vi.fn();
  const fetch = vi.fn((_url: string, options: RequestInit) => {
    signal = options.signal!;
    return new Promise<Response>((resolve) => {
      finish = resolve;
    });
  });
  vi.stubGlobal("fetch", fetch);
  const { unmount } = render(
    <TransactionDialog {...props} onRecorded={recorded} />,
  );
  fireEvent.change(screen.getByLabelText("Transaction type"), {
    target: { value: "FEE" },
  });
  fireEvent.change(screen.getByLabelText("Currency"), {
    target: { value: "USD" },
  });
  fireEvent.change(screen.getByLabelText("Cash amount"), {
    target: { value: "1" },
  });
  const submit = screen.getByRole("button", { name: "Record transaction" });
  fireEvent.click(submit);
  fireEvent.submit(submit.closest("form")!);
  expect(fetch).toHaveBeenCalledOnce();
  expect(screen.getByRole("button", { name: "Recording…" })).toBeDisabled();
  unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => {
    finish(Response.json({}));
  });
  expect(recorded).not.toHaveBeenCalled();
});
it("renders exact negative cash and separate gross income/tax without approximate or combined net values", () => {
  render(
    <MoneyView
      data={summary}
      asOf={summary.as_of_date}
      setAsOf={vi.fn()}
      account
      noHistory={false}
    />,
  );
  expect(
    screen.getByText("−9,007,199,254,740,993.12345678 USD"),
  ).toBeInTheDocument();
  expect(screen.getByText("Taxes paid or withheld")).toBeInTheDocument();
  expect(screen.queryByText(/≈|Net income|Net P&L/)).not.toBeInTheDocument();
});
it.each([null, false, 0, { currencies: [] }])(
  "reports malformed top-level Money payload %j",
  (payload) => {
    render(
      <MoneyView
        data={payload as unknown as MoneySummary}
        asOf={summary.as_of_date}
        setAsOf={vi.fn()}
        account
        noHistory={false}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unable to display Money",
    );
  },
);
it.each(["-0", "1E-8", "1.000000001", "NaN", "01", "1.00"])(
  "rejects malformed money %s",
  (value) => {
    expect(() => formatCash(value, "USD")).toThrow();
    render(
      <MoneyView
        data={{ ...summary, currencies: [{ ...bucket, cash_balance: value }] }}
        asOf={summary.as_of_date}
        setAsOf={vi.fn()}
        account
        noHistory={false}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unable to display Money",
    );
  },
);
it("retains active zero currency and distinguishes pre-cutoff inactivity", () => {
  const { rerender } = render(
    <MoneyView
      data={{ ...summary, currencies: [{ ...bucket, cash_balance: "0" }] }}
      asOf={summary.as_of_date}
      setAsOf={vi.fn()}
      account
      noHistory={false}
    />,
  );
  expect(screen.getAllByText("0 USD").length).toBeGreaterThan(0);
  rerender(
    <MoneyView
      data={{ ...summary, currencies: [] }}
      asOf={summary.as_of_date}
      setAsOf={vi.fn()}
      account
      noHistory={false}
    />,
  );
  expect(
    screen.getByText("No recorded cash activity through this date."),
  ).toBeInTheDocument();
});
it.each([
  "DEPOSIT",
  "WITHDRAWAL",
  "BUY",
  "SELL",
  "DIVIDEND",
  "COUPON",
  "FEE",
  "TAX",
])(
  "History offers corrections for %s without irrelevant placeholders",
  (type) => {
    render(
      <History
        transactions={[{ ...parent, type }]}
        instruments={instruments}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Delete" })).toHaveLength(2);
    if (!["BUY", "SELL"].includes(type))
      expect(screen.queryByText(/Quantity|Price/)).not.toBeInTheDocument();
  },
);
