import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import Workspace from "./workspace";
import { localDate } from "./entry-dialogs";

afterEach(() => vi.unstubAllGlobals());
function response(url: string) {
  if (url === "/api/portfolios") return [{ id: 1, name: "Portfolio" }];
  if (url.endsWith("/accounts"))
    return [
      { id: 3, portfolio_id: 1, name: "A" },
      { id: 4, portfolio_id: 1, name: "B" },
    ];
  if (
    url === "/api/instruments" ||
    url.endsWith("/positions") ||
    url.endsWith("/transactions")
  )
    return [];
  if (url.includes("/money-summary?"))
    return { as_of_date: url.split("=")[1], currencies: [] };
  return {
    metric: "GROSS_TRADE_CASH_REALISED_PNL",
    resolved_pnl_by_currency: [],
    unresolved_components: [],
    is_fully_resolved: true,
  };
}

it("Money date refetches only Money, preserves within tabs, resets on context and permits future dates", async () => {
  const requests: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      requests.push(url);
      return Response.json(response(url));
    }),
  );
  render(<Workspace />);
  await waitFor(() =>
    expect(screen.getByLabelText("Account")).toHaveValue("3"),
  );
  fireEvent.click(screen.getByRole("tab", { name: "Money" }));
  expect(screen.getByLabelText("As of date")).toHaveValue(localDate());
  await screen.findByText("No transactions yet.");
  requests.length = 0;
  fireEvent.change(screen.getByLabelText("As of date"), {
    target: { value: "2099-01-01" },
  });
  await waitFor(() =>
    expect(requests).toEqual([
      "/api/accounts/3/money-summary?as_of_date=2099-01-01",
    ]),
  );
  fireEvent.click(screen.getByRole("tab", { name: "History" }));
  fireEvent.click(screen.getByRole("tab", { name: "Money" }));
  expect(screen.getByLabelText("As of date")).toHaveValue("2099-01-01");
  expect(requests).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Account"), {
    target: { value: "4" },
  });
  fireEvent.click(screen.getByRole("tab", { name: "Money" }));
  expect(screen.getByLabelText("As of date")).toHaveValue(localDate());
  await waitFor(() =>
    expect(requests).toContain(
      `/api/accounts/4/money-summary?as_of_date=${localDate()}`,
    ),
  );
  fireEvent.change(screen.getByLabelText("Account"), {
    target: { value: "summary" },
  });
  fireEvent.click(screen.getByRole("tab", { name: "Money" }));
  await screen.findByText("No recorded cash activity through this date.");
  expect(screen.getByLabelText("As of date")).toHaveValue(localDate());
  expect(
    screen.queryByRole("button", { name: "Record transaction" }),
  ).not.toBeInTheDocument();
});

it("ignores a delayed Money response from an obsolete cutoff", async () => {
  let finish!: (value: Response) => void;
  let oldSignal!: AbortSignal;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      if (url.endsWith("as_of_date=2019-01-01")) {
        oldSignal = options.signal!;
        return new Promise<Response>((resolve) => {
          finish = resolve;
        });
      }
      return Response.json(response(url));
    }),
  );
  render(<Workspace />);
  await waitFor(() =>
    expect(screen.getByLabelText("Account")).toHaveValue("3"),
  );
  fireEvent.click(screen.getByRole("tab", { name: "Money" }));
  fireEvent.change(screen.getByLabelText("As of date"), {
    target: { value: "2019-01-01" },
  });
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.change(screen.getByLabelText("As of date"), {
    target: { value: "2020-01-01" },
  });
  await screen.findByText("No transactions yet.");
  expect(oldSignal.aborted).toBe(true);
  finish(
    Response.json({
      as_of_date: "2019-01-01",
      currencies: [{ currency_code: "USD", cash_balance: "bad" }],
    }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("As of date")).toHaveValue("2020-01-01"),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
