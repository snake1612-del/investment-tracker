"use client";
import { useEffect, useRef, useState } from "react";
import { Dialog } from "./dialog";

type Diagnostic = {
  row_number?: number | null;
  row_id?: string | null;
  field: string;
  code: string;
  message: string;
};
export function CsvImportDialog({
  accountId,
  onClose,
  onImported,
}: {
  accountId: number;
  onClose: () => void;
  onImported: (message: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    setDiagnostics([]);
    try {
      const response = await fetch(
        `/api/accounts/${accountId}/transaction-imports/csv`,
        {
          method: "POST",
          headers: { "Content-Type": "text/csv; charset=utf-8" },
          body: file,
          signal: controller.signal,
          cache: "no-store",
        },
      );
      const payload = await response.json();
      if (controller.signal.aborted) return;
      if (!response.ok) {
        if (response.status === 422 && Array.isArray(payload.detail)) {
          setDiagnostics(payload.detail);
          setError(
            "The file was not imported. Correct all reported errors and retry.",
          );
        } else
          setError(
            response.status === 404
              ? "The selected Account no longer exists. Refresh the workspace."
              : "Import failed. Retry the same file safely; no partial import is committed.",
          );
      } else if (["IMPORTED", "ALREADY_IMPORTED"].includes(payload.status)) {
        onImported(
          payload.status === "ALREADY_IMPORTED"
            ? "Already imported. No new transactions were created."
            : `Imported ${payload.row_count} transactions.`,
        );
      } else throw new Error("Unexpected import response");
    } catch {
      if (!controller.signal.aborted)
        setError(
          "Unable to confirm import. Retry the same file safely: a committed source will not be duplicated.",
        );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <Dialog title="Import normalized CSV" busy={busy} onClose={onClose}>
      <form onSubmit={submit}>
        <p>
          Import into this Account only. Use normalized CSV v1 with existing
          Instrument IDs. All rows commit together; no automatic Instrument
          matching.
        </p>
        <label>
          CSV file
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={busy}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setError("");
              setDiagnostics([]);
            }}
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {diagnostics.length > 0 && (
          <ul>
            {diagnostics.map((item, index) => (
              <li key={index}>
                Line {item.row_number ?? "file"}
                {item.row_id ? ` · ${item.row_id}` : ""} · {item.field} ·{" "}
                {item.code}: {item.message}
              </li>
            ))}
          </ul>
        )}
        <button type="submit" disabled={!file || busy}>
          {busy ? "Importing…" : "Import"}
        </button>
      </form>
    </Dialog>
  );
}
