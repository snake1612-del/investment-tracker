import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TransactionDialog } from "./entry-dialogs";

describe("transaction entry", () => {
  beforeEach(() => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute("open");
    };
  });
  afterEach(() => vi.unstubAllGlobals());
  const props = {
    accountId: 1,
    instruments: [
      { id: 2, name: "Fund" },
      { id: 3, name: "Fund" },
    ],
    positions: [],
    onClose: vi.fn(),
    onRecorded: vi.fn(),
    onInstrumentCreated: vi.fn(),
  };
  it("validates deposit fields without submitting", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(<TransactionDialog {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Record transaction" }));
    expect(
      screen.getByText("Use exactly 3 Latin letters."),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("records a valid deposit as a string and keeps server validation visible", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json(
          {
            detail: [{ loc: ["body", "cash_amount"], msg: "Rejected amount" }],
          },
          { status: 422 },
        ),
      )
      .mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetch);
    const recorded = vi.fn();
    render(<TransactionDialog {...props} onRecorded={recorded} />);
    fireEvent.change(screen.getByLabelText("Currency"), {
      target: { value: "eur" },
    });
    fireEvent.change(screen.getByLabelText("Cash amount"), {
      target: { value: "9007199254740993,25" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Record transaction" }));
    expect(await screen.findByText("Rejected amount")).toBeInTheDocument();
    expect(recorded).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Record transaction" }));
    await waitFor(() => expect(recorded).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({
      cash_amount: "9007199254740993.25",
      currency_code: "EUR",
    });
    expect(JSON.parse(fetch.mock.calls[1][1].body)).not.toHaveProperty(
      "quantity",
    );
  });
  it.each(["BUY", "SELL"])(
    "preserves independent %s facts, comma normalization, and prevents duplicate submit",
    async (type) => {
      let finish!: (response: Response) => void;
      const fetch = vi.fn<
        (url: string, options: RequestInit) => Promise<Response>
      >(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      );
      vi.stubGlobal("fetch", fetch);
      const recorded = vi.fn();
      render(<TransactionDialog {...props} onRecorded={recorded} />);
      fireEvent.change(screen.getByLabelText("Transaction type"), {
        target: { value: type },
      });
      expect(
        screen.getByRole("option", { name: "Fund · #2" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("option", { name: "Fund · #3" }),
      ).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText("Instrument"), {
        target: { value: "2" },
      });
      for (const [label, value] of [
        ["Currency", "usd"],
        ["Quantity", "2"],
        ["Price", "5"],
        ["Cash amount", "99,5"],
      ])
        fireEvent.change(screen.getByLabelText(label), { target: { value } });
      if (type === "SELL")
        expect(screen.getByText(/This sell exceeds/)).toBeInTheDocument();
      const submit = screen.getByRole("button", { name: "Record transaction" });
      fireEvent.click(submit);
      fireEvent.submit(submit.closest("form")!);
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: "Recording…" })).toBeDisabled();
      const body = JSON.parse(String(fetch.mock.calls[0][1].body));
      expect(body).toMatchObject({
        instrument_id: 2,
        quantity: "2",
        price: "5",
        cash_amount: "99.5",
        currency_code: "USD",
      });
      finish(new Response("{}", { status: 201 }));
      await waitFor(() => expect(recorded).toHaveBeenCalledTimes(1));
    },
  );
});
