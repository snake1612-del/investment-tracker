import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CorrectionDialog } from "./correction-dialog";
import { History } from "./workspace-views";
import type { Transaction } from "../lib/api";

const transaction: Transaction = {
  id: 7,
  account_id: 1,
  instrument_id: 2,
  related_transaction_id: null,
  type: "BUY",
  effective_date: "2020-01-01",
  settlement_date: "2020-01-03",
  currency_code: "USD",
  quantity: "2.000000000001",
  price: "5.000000000001",
  cash_amount: "9007199254740993.25",
};
const instruments = [
  { id: 2, name: "Fund" },
  { id: 3, name: "Other" },
];
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => vi.unstubAllGlobals());
function props() {
  return {
    transaction,
    instruments,
    deleting: false,
    onClose: vi.fn(),
    onCorrected: vi.fn(),
  };
}

it.each(["BUY", "SELL"])(
  "prefills exact %s facts and sends complete PUT with cleared settlement",
  async (type) => {
    const fetch = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetch);
    const settings = { ...props(), transaction: { ...transaction, type } };
    render(<CorrectionDialog {...settings} />);
    expect(screen.getByLabelText("Cash amount")).toHaveValue(
      transaction.cash_amount,
    );
    expect(screen.getByLabelText("Quantity")).toHaveValue(transaction.quantity);
    expect(screen.getByLabelText("Settlement date (optional)")).toHaveValue(
      "2020-01-03",
    );
    expect(screen.queryByLabelText("Transaction type")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Settlement date (optional)"), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText("Instrument"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(settings.onCorrected).toHaveBeenCalledOnce());
    expect(fetch.mock.calls[0][0]).toBe("/api/accounts/1/transactions/7");
    expect(fetch.mock.calls[0][1].method).toBe("PUT");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      instrument_id: 3,
      effective_date: "2020-01-01",
      currency_code: "USD",
      quantity: transaction.quantity,
      price: transaction.price,
      cash_amount: transaction.cash_amount,
      settlement_date: null,
    });
  },
);
it("deposit edit sends only deposit facts", async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({}));
  vi.stubGlobal("fetch", fetch);
  const settings = {
    ...props(),
    transaction: { ...transaction, type: "DEPOSIT", instrument_id: null },
  };
  render(<CorrectionDialog {...settings} />);
  expect(screen.queryByLabelText("Quantity")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(settings.onCorrected).toHaveBeenCalledOnce());
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    effective_date: "2020-01-01",
    currency_code: "USD",
    cash_amount: transaction.cash_amount,
  });
});
it("validates without submitting and keeps failed input editable", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      Response.json(
        { detail: [{ loc: ["body", "quantity"], msg: "Rejected quantity" }] },
        { status: 422 },
      ),
    );
  vi.stubGlobal("fetch", fetch);
  const settings = props();
  render(<CorrectionDialog {...settings} />);
  fireEvent.change(screen.getByLabelText("Quantity"), {
    target: { value: "0" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Quantity"), {
    target: { value: "3" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Please check the entered fields.",
  );
  expect(screen.getByText("Rejected quantity")).toBeInTheDocument();
  expect(settings.onCorrected).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Quantity")).toHaveValue("3");
});
it("requires explicit deletion, handles empty 204 and prevents duplicate submit", async () => {
  let finish!: (response: Response) => void;
  const fetch = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
  );
  vi.stubGlobal("fetch", fetch);
  const settings = { ...props(), deleting: true };
  render(<CorrectionDialog {...settings} />);
  expect(screen.getByText(/permanently deletes/)).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  const button = screen.getByRole("button", { name: "Delete permanently" });
  fireEvent.click(button);
  fireEvent.submit(button.closest("form")!);
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[0]).toBeDefined();
  expect(screen.getByRole("button", { name: "Close dialog" })).toBeDisabled();
  finish(new Response(null, { status: 204 }));
  await waitFor(() => expect(settings.onCorrected).toHaveBeenCalledOnce());
});
it("does not report a correction into a different account after unmount", async () => {
  let finish!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    ),
  );
  const settings = props();
  const view = render(<CorrectionDialog {...settings} />);
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  view.unmount();
  await act(async () => {
    finish(Response.json({}));
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(settings.onCorrected).not.toHaveBeenCalled();
});
it("shows a contextual DELETE conflict without closing or retrying", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      Response.json({ detail: "Persistence conflict" }, { status: 409 }),
    );
  vi.stubGlobal("fetch", fetch);
  const settings = { ...props(), deleting: true };
  render(<CorrectionDialog {...settings} />);
  fireEvent.click(screen.getByRole("button", { name: "Delete permanently" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Fee or Tax transaction is linked",
  );
  expect(settings.onCorrected).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[0][0]).toBe("/api/accounts/1/transactions/7");
  expect(fetch.mock.calls[0][1].method).toBe("DELETE");
  expect(fetch.mock.calls[0][1].body).toBeUndefined();
});
it("does not offer unsupported History corrections", () => {
  const edit = vi.fn(),
    remove = vi.fn();
  render(
    <History
      transactions={[{ ...transaction, type: "FUTURE" }]}
      instruments={instruments}
      onEdit={edit}
      onDelete={remove}
    />,
  );
  expect(
    screen.queryByRole("button", { name: "Edit" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Delete" }),
  ).not.toBeInTheDocument();
});
