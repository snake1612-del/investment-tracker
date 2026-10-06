import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { MarketPrices } from "./market-prices";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => vi.unstubAllGlobals());

it("saves exact zero and preserves conflict feedback without closing dialog", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === "/api/instruments")
        return Response.json([{ id: 1, name: "Fund" }]);
      if (init?.method === "POST")
        return Response.json(
          { detail: "Persistence constraint conflict" },
          { status: 409 },
        );
      return Response.json([]);
    });
  vi.stubGlobal("fetch", fetch);
  const changed = vi.fn();
  render(<MarketPrices onChanged={changed} />);
  expect(
    await screen.findByText("No market prices recorded."),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Add market price" }));
  fireEvent.change(screen.getByLabelText("Unit market price"), {
    target: { value: "0" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save market price" }));
  await waitFor(() =>
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Nothing was saved or removed",
    ),
  );
  const call = fetch.mock.calls.find(([, init]) => init?.method === "POST")!;
  expect(JSON.parse(call[1].body)).toMatchObject({
    price: "0",
    currency_code: "USD",
  });
  expect(changed).not.toHaveBeenCalled();
});

it("rejects negative and overprecision prices before submission", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string) =>
      Response.json(
        url === "/api/instruments" ? [{ id: 1, name: "Fund" }] : [],
      ),
    );
  vi.stubGlobal("fetch", fetch);
  render(<MarketPrices onChanged={vi.fn()} />);
  await screen.findByText("No market prices recorded.");
  fireEvent.click(screen.getByRole("button", { name: "Add market price" }));
  for (const value of ["-1", "1E-13", "10000000000000000"]) {
    fireEvent.change(screen.getByLabelText("Unit market price"), {
      target: { value },
    });
    expect(
      screen.getByRole("button", { name: "Save market price" }),
    ).toBeDisabled();
  }
  expect(fetch.mock.calls.every(([, init]) => init?.method === "GET")).toBe(
    true,
  );
});
