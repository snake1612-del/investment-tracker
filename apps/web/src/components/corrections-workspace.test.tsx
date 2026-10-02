import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Workspace from "./workspace";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => vi.unstubAllGlobals());

it.each(["PUT", "DELETE"])(
  "refreshes all Account reads after %s, keeps selection and reloads Portfolio summary",
  async (method) => {
    let mutated = false;
    const reads: string[] = [];
    const fetch = vi.fn(async (url: string, options: RequestInit) => {
      if (options.method === "PUT" || options.method === "DELETE") {
        expect(url).toBe("/api/accounts/3/transactions/7");
        expect(options.method).toBe(method);
        mutated = true;
        return options.method === "DELETE"
          ? new Response(null, { status: 204 })
          : Response.json({});
      }
      reads.push(url);
      if (url === "/api/portfolios")
        return Response.json([{ id: 1, name: "Portfolio" }]);
      if (url.endsWith("/accounts"))
        return Response.json([{ id: 3, portfolio_id: 1, name: "Account" }]);
      if (url === "/api/instruments")
        return Response.json([{ id: 2, name: "Fund" }]);
      if (url.endsWith("/transactions"))
        return Response.json(
          mutated && method === "DELETE"
            ? []
            : [
                {
                  id: 7,
                  account_id: 3,
                  instrument_id: 2,
                  type: "BUY",
                  effective_date: "2020-01-01",
                  settlement_date: null,
                  currency_code: "USD",
                  quantity: mutated ? "3" : "2",
                  price: "5",
                  cash_amount: "11",
                },
              ],
        );
      if (url.endsWith("/positions"))
        return Response.json([
          {
            instrument_id: 2,
            instrument_name: "Fund",
            quantity: mutated ? "3" : "2",
          },
        ]);
      return Response.json({
        metric: "GROSS_TRADE_CASH_REALISED_PNL",
        resolved_pnl_by_currency: [],
        unresolved_components: [],
        is_fully_resolved: true,
      });
    });
    vi.stubGlobal("fetch", fetch);
    render(<Workspace />);
    await waitFor(() =>
      expect(screen.getByLabelText("Account")).toHaveValue("3"),
    );
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    const row = await screen.findByRole("row", { name: /BUY/ });
    fireEvent.click(
      within(row).getByRole("button", {
        name: method === "PUT" ? "Edit" : "Delete",
      }),
    );
    if (method === "PUT")
      fireEvent.change(screen.getByLabelText("Quantity"), {
        target: { value: "3" },
      });
    reads.length = 0;
    fireEvent.click(
      screen.getByRole("button", {
        name: method === "PUT" ? "Save changes" : "Delete permanently",
      }),
    );
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      for (const path of ["transactions", "positions", "realised-pnl"])
        expect(reads).toContain(`/api/accounts/3/${path}`);
    });
    expect(screen.getByLabelText("Account")).toHaveValue("3");
    if (method === "DELETE")
      expect(
        await screen.findByText("No transactions yet"),
      ).toBeInTheDocument();
    else
      expect(
        within(screen.getByRole("row", { name: /BUY/ })).getByText("3"),
      ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Account"), {
      target: { value: "summary" },
    });
    await waitFor(() => expect(reads).toContain("/api/portfolios/1/positions"));
    expect(reads).toContain("/api/portfolios/1/realised-pnl");
    expect(
      screen.queryByRole("tab", { name: "History" }),
    ).not.toBeInTheDocument();
  },
);
