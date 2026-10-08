import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { CsvImportDialog } from "./csv-import-dialog";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => vi.unstubAllGlobals());
const file = new File(["\ufeffraw exact source\r\n"], "synthetic.csv", {
  type: "text/csv",
});
function selectFile() {
  fireEvent.change(screen.getByLabelText("CSV file"), {
    target: { files: [file] },
  });
}

it.each(["IMPORTED", "ALREADY_IMPORTED"])(
  "sends one raw file and reports %s",
  async (status) => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        Response.json(
          { status, row_count: 3 },
          { status: status === "IMPORTED" ? 201 : 200 },
        ),
      );
    vi.stubGlobal("fetch", fetch);
    const imported = vi.fn();
    render(
      <CsvImportDialog accountId={7} onClose={vi.fn()} onImported={imported} />,
    );
    expect(screen.getByRole("button", { name: "Import" })).toBeDisabled();
    selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() => expect(imported).toHaveBeenCalledOnce());
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0][0]).toBe(
      "/api/accounts/7/transaction-imports/csv",
    );
    expect(fetch.mock.calls[0][1]).toMatchObject({
      method: "POST",
      body: file,
      headers: { "Content-Type": "text/csv; charset=utf-8" },
    });
    expect(imported.mock.calls[0][0]).toMatch(
      status === "IMPORTED" ? /Imported 3/ : /No new transactions/,
    );
  },
);

it("shows deterministic line diagnostics without claiming success, then retries the same file", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        {
          detail: [
            {
              row_number: 3,
              row_id: "child",
              field: "related_row_id",
              code: "RELATED_ROW_NOT_FOUND",
              message: "Parent missing",
            },
          ],
        },
        { status: 422 },
      ),
    )
    .mockResolvedValue(
      Response.json({ status: "IMPORTED", row_count: 2 }, { status: 201 }),
    );
  vi.stubGlobal("fetch", fetch);
  const imported = vi.fn();
  render(
    <CsvImportDialog accountId={7} onClose={vi.fn()} onImported={imported} />,
  );
  selectFile();
  fireEvent.click(screen.getByRole("button", { name: "Import" }));
  expect(
    await screen.findByText(
      /Line 3 · child · related_row_id · RELATED_ROW_NOT_FOUND: Parent missing/,
    ),
  ).toBeInTheDocument();
  expect(imported).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Import" }));
  await waitFor(() => expect(imported).toHaveBeenCalledOnce());
  expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
});

it.each([404, 500, "network"])(
  "keeps %s failure visible with safe retry",
  async (status) => {
    const fetch =
      status === "network"
        ? vi.fn().mockRejectedValue(new Error("offline"))
        : vi
            .fn()
            .mockResolvedValue(
              Response.json(
                { detail: "failure" },
                { status: status as number },
              ),
            );
    vi.stubGlobal("fetch", fetch);
    const imported = vi.fn();
    render(
      <CsvImportDialog accountId={7} onClose={vi.fn()} onImported={imported} />,
    );
    selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      status === 404 ? /no longer exists/ : /Retry the same file safely/,
    );
    expect(imported).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Import" })).toBeEnabled(),
    );
  },
);

it("prevents duplicate submit and aborts on unmount without a stale success callback", async () => {
  let finish!: (response: Response) => void;
  const fetch = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
  );
  vi.stubGlobal("fetch", fetch);
  const imported = vi.fn();
  const view = render(
    <CsvImportDialog accountId={7} onClose={vi.fn()} onImported={imported} />,
  );
  selectFile();
  fireEvent.click(screen.getByRole("button", { name: "Import" }));
  expect(screen.getByRole("button", { name: "Importing…" })).toBeDisabled();
  expect(screen.getByLabelText("CSV file")).toBeDisabled();
  const options = fetch.mock.calls[0] as unknown as [string, RequestInit];
  view.unmount();
  expect(options[1].signal?.aborted).toBe(true);
  finish(Response.json({ status: "IMPORTED", row_count: 1 }));
  await Promise.resolve();
  expect(imported).not.toHaveBeenCalled();
});
