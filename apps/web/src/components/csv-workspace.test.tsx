import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
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

it.each(["IMPORTED", "ALREADY_IMPORTED"])(
  "refreshes derived reads after %s and has no Portfolio import flow",
  async (status) => {
    const reads: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options: RequestInit) => {
        if (options.method === "POST")
          return Response.json(
            { status, row_count: 1 },
            { status: status === "IMPORTED" ? 201 : 200 },
          );
        reads.push(url);
        if (url === "/api/portfolios")
          return Response.json([{ id: 1, name: "Portfolio" }]);
        if (url.endsWith("/accounts"))
          return Response.json([{ id: 3, portfolio_id: 1, name: "Account" }]);
        if (
          url === "/api/instruments" ||
          url.endsWith("/transactions") ||
          url.endsWith("/positions")
        )
          return Response.json([]);
        return Response.json({
          resolved_pnl_by_currency: [],
          unresolved_components: [],
          is_fully_resolved: true,
        });
      }),
    );
    render(<Workspace />);
    await waitFor(() =>
      expect(screen.getByLabelText("Account")).toHaveValue("3"),
    );
    fireEvent.click(screen.getByRole("tab", { name: "Valuation" }));
    await waitFor(() =>
      expect(
        reads.some((path) => path.startsWith("/api/accounts/3/valuation?")),
      ).toBe(true),
    );
    fireEvent.click(screen.getByRole("button", { name: "Import CSV" }));
    fireEvent.change(screen.getByLabelText("CSV file"), {
      target: { files: [new File(["csv"], "file.csv")] },
    });
    reads.length = 0;
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      for (const path of ["transactions", "positions", "realised-pnl"])
        expect(reads).toContain(`/api/accounts/3/${path}`);
      expect(
        reads.some((path) => path.startsWith("/api/accounts/3/money-summary?")),
      ).toBe(true);
      expect(
        reads.some((path) => path.startsWith("/api/accounts/3/valuation?")),
      ).toBe(true);
    });
    expect(screen.getByLabelText("Account")).toHaveValue("3");
    fireEvent.change(screen.getByLabelText("Account"), {
      target: { value: "summary" },
    });
    await waitFor(() => expect(reads).toContain("/api/portfolios/1/positions"));
    expect(
      screen.queryByRole("button", { name: "Import CSV" }),
    ).not.toBeInTheDocument();
  },
);
