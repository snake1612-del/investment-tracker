import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Home from "./page";

describe("Home", () => {
  beforeEach(() => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute("open");
    };
  });
  afterEach(() => vi.unstubAllGlobals());
  it.each(["Account", "summary", "removed Account"])(
    "preserves or safely invalidates %s through delayed discovery refresh",
    async (scenario) => {
      const portfolios = [{ id: 1, name: "Portfolio" }];
      const accounts = [
        { id: 3, portfolio_id: 1, name: "First" },
        { id: 4, portfolio_id: 1, name: "Second" },
      ];
      let portfolioReads = 0;
      let accountReads = 0;
      let finishPortfolios!: (response: Response) => void;
      let finishAccounts!: (response: Response) => void;
      const writes: { url: string; body: unknown }[] = [];
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string, options: RequestInit) => {
          if (options.method === "POST") {
            writes.push({ url, body: JSON.parse(String(options.body)) });
            return Response.json({});
          }
          if (url === "/api/portfolios") {
            if (++portfolioReads === 1) return Response.json(portfolios);
            return new Promise<Response>((resolve) => {
              finishPortfolios = resolve;
            });
          }
          if (url === "/api/portfolios/1/accounts") {
            if (++accountReads === 1) return Response.json(accounts);
            return new Promise<Response>((resolve) => {
              finishAccounts = resolve;
            });
          }
          if (url.endsWith("/realised-pnl"))
            return Response.json({
              metric: "GROSS_TRADE_CASH_REALISED_PNL",
              resolved_pnl_by_currency: [],
              unresolved_components: [],
              is_fully_resolved: true,
            });
          return Response.json([]);
        }),
      );
      render(<Home />);
      await waitFor(() =>
        expect(screen.getByLabelText("Account")).toHaveValue("3"),
      );
      fireEvent.change(screen.getByLabelText("Account"), {
        target: { value: scenario === "summary" ? "summary" : "4" },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Refresh portfolios" }),
      );
      expect(screen.getByText("Loading workspace…")).toBeInTheDocument();
      finishPortfolios(Response.json(portfolios));
      expect(await screen.findByText("Loading accounts…")).toBeInTheDocument();
      finishAccounts(
        Response.json(
          scenario === "removed Account" ? [accounts[0]] : accounts,
        ),
      );
      const expected = scenario === "Account" ? "4" : "summary";
      await waitFor(() => {
        expect(screen.getByLabelText("Account")).not.toBeDisabled();
        expect(screen.getByLabelText("Account")).toHaveValue(expected);
      });
      if (scenario !== "Account") {
        expect(
          screen.queryByRole("tab", { name: "History" }),
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole("button", { name: "Record transaction" }),
        ).not.toBeInTheDocument();
        expect(writes).toEqual([]);
        if (scenario === "summary") return;
        expect(
          screen.getByText(/selected Account is no longer available/),
        ).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText("Account"), {
          target: { value: "3" },
        });
      }
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: "Record transaction" }),
        ).not.toBeDisabled(),
      );
      fireEvent.click(
        screen.getByRole("button", { name: "Record transaction" }),
      );
      fireEvent.change(screen.getByLabelText("Currency"), {
        target: { value: "USD" },
      });
      fireEvent.change(screen.getByLabelText("Cash amount"), {
        target: { value: "10" },
      });
      fireEvent.click(
        within(screen.getByRole("dialog")).getByRole("button", {
          name: "Record transaction",
        }),
      );
      await waitFor(() =>
        expect(writes).toEqual([
          {
            url: `/api/accounts/${scenario === "Account" ? 4 : 3}/deposits`,
            body: expect.objectContaining({
              currency_code: "USD",
              cash_amount: "10",
            }),
          },
        ]),
      );
    },
  );
  it("switches canonical Portfolio/Account contexts, resets invalid Account and ignores stale responses", async () => {
    let delayed!: (response: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/portfolios")
          return Response.json([
            { id: 1, name: "Same" },
            { id: 2, name: "Same" },
          ]);
        if (url === "/api/portfolios/1/accounts")
          return Response.json([
            { id: 3, portfolio_id: 1, name: "First" },
            { id: 4, portfolio_id: 1, name: "Second" },
          ]);
        if (url === "/api/portfolios/2/accounts")
          return Response.json([{ id: 5, portfolio_id: 2, name: "Third" }]);
        if (url === "/api/accounts/4/positions")
          return new Promise<Response>((resolve) => {
            delayed = resolve;
          });
        if (url.endsWith("/realised-pnl"))
          return Response.json({
            metric: "GROSS_TRADE_CASH_REALISED_PNL",
            resolved_pnl_by_currency: [],
            unresolved_components: [],
            is_fully_resolved: true,
          });
        return Response.json([]);
      }),
    );
    render(<Home />);
    await waitFor(() =>
      expect(screen.getByLabelText("Account")).toHaveValue("3"),
    );
    fireEvent.change(screen.getByLabelText("Account"), {
      target: { value: "4" },
    });
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Second" }),
      ).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByLabelText("Portfolio"), {
      target: { value: "2" },
    });
    await waitFor(() =>
      expect(screen.getByLabelText("Account")).toHaveValue("5"),
    );
    delayed(
      Response.json([
        { instrument_id: 1, instrument_name: "Stale holding", quantity: "99" },
      ]),
    );
    await waitFor(() =>
      expect(screen.getByText("No holdings yet")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Stale holding")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Holdings" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
  it("shows technical server errors and permits a successful retry", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 500 }))
      .mockResolvedValue(Response.json([]));
    vi.stubGlobal("fetch", fetch);
    render(<Home />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
    expect(
      screen.queryByText("No realised activity yet"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByText("Start your investment journal"),
    ).toBeInTheDocument();
  });
  it("creates and automatically selects Portfolio and Account without manual IDs", async () => {
    const portfolios: object[] = [];
    const accounts: object[] = [];
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options: RequestInit) => {
        requests.push(url);
        const body = options.body
          ? JSON.parse(String(options.body))
          : undefined;
        let result: unknown = [];
        if (url === "/api/portfolios") {
          if (body) {
            const created = { id: 8, ...body };
            portfolios.push(created);
            result = created;
          } else result = portfolios;
        } else if (url.endsWith("/accounts")) {
          if (body) {
            const created = { id: 9, portfolio_id: 8, ...body };
            accounts.push(created);
            result = created;
          } else result = accounts;
        } else if (url.endsWith("/realised-pnl"))
          result = {
            metric: "GROSS_TRADE_CASH_REALISED_PNL",
            resolved_pnl_by_currency: [],
            unresolved_components: [],
            is_fully_resolved: true,
          };
        return new Response(JSON.stringify(result), { status: 200 });
      }),
    );
    render(<Home />);
    expect(
      await screen.findByText("Start your investment journal"),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Create your first Portfolio" }),
    );
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Name"), {
      target: { value: "Retirement" },
    });
    fireEvent.change(dialog.getByLabelText("Base currency"), {
      target: { value: "usd" },
    });
    fireEvent.click(dialog.getByRole("button", { name: "Create Portfolio" }));
    expect(
      await screen.findByText("This Portfolio has no Accounts yet."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Portfolio")).toHaveValue("8");
    expect(
      screen.queryByRole("tab", { name: "History" }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Create your first Account" }),
    );
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Broker" },
    });
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Create Account",
      }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Account")).toHaveValue("9"),
    );
    expect(
      await screen.findByRole("tab", { name: "History" }),
    ).toBeInTheDocument();
    expect(requests).toContain("/api/accounts/9/positions");
    fireEvent.change(screen.getByLabelText("Account"), {
      target: { value: "summary" },
    });
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Record transaction" }),
      ).not.toBeInTheDocument(),
    );
  });
});
