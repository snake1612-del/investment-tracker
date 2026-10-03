"use client";
import { useEffect, useState } from "react";
import {
  api,
  type Account,
  type Entity,
  type Position,
  type Realised,
  type Transaction,
} from "../lib/api";
import {
  EntityDialog,
  TransactionDialog,
  localDate,
  dateError,
} from "./entry-dialogs";
import { MoneyView, type MoneySummary } from "./money-view";
import { CorrectionDialog } from "./correction-dialog";
import { History, Holdings, RealisedResult } from "./workspace-views";

function useRead<T>(path: string | null, revision = 0) {
  const [state, setState] = useState<{
    data?: T;
    error?: string;
    loading: boolean;
    path?: string | null;
    revision?: number;
  }>({ loading: true });
  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    api<T>(path, undefined, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted)
          setState({ data, loading: false, path, revision });
      },
      (error) => {
        if (!controller.signal.aborted)
          setState({ error: error.message, loading: false, path, revision });
      },
    );
    return () => controller.abort();
  }, [path, revision]);
  return path === null
    ? { loading: false, data: undefined, error: undefined }
    : state.path === path && state.revision === revision
      ? state
      : { loading: true, data: undefined, error: undefined };
}

export default function Workspace() {
  const [revision, setRevision] = useState(0);
  const portfolios = useRead<Entity[]>("/portfolios", revision);
  const [selected, setSelected] = useState("");
  const [accountSelection, setAccountSelection] = useState<{
    portfolioId: number;
    value: string;
  } | null>(null);
  const [creating, setCreating] = useState(false);
  const [feedback, setFeedback] = useState("");
  const active =
    portfolios.data?.find((p) => String(p.id) === selected) ??
    portfolios.data?.[0];
  return (
    <main className="workspace">
      <header className="masthead">
        <div>
          <p className="eyebrow">Your manual investment journal</p>
          <h1>Investment Tracker</h1>
        </div>
        <span className="journal-label">Portfolio workspace</span>
      </header>
      {feedback && (
        <p className="success" role="status">
          {feedback}
        </p>
      )}
      <section className="context">
        <label>
          Portfolio
          <select
            aria-label="Portfolio"
            value={active?.id ?? ""}
            onChange={(e) => {
              setSelected(e.target.value);
              setAccountSelection(null);
              setFeedback("");
            }}
            disabled={portfolios.loading}
          >
            <option value="" disabled>
              {portfolios.loading ? "Loading portfolios…" : "Select Portfolio"}
            </option>
            {portfolios.data?.map((p) => (
              <option value={p.id} key={p.id}>
                {p.name} · #{p.id}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary" onClick={() => setCreating(true)}>
          Create Portfolio
        </button>
        <button
          className="secondary"
          disabled={portfolios.loading}
          onClick={() => setRevision((r) => r + 1)}
        >
          Refresh portfolios
        </button>
      </section>
      {selected &&
        portfolios.data &&
        !portfolios.data.some((p) => String(p.id) === selected) && (
          <p className="notice">
            The selected Portfolio is no longer available. Choose an available
            Portfolio or create one.
          </p>
        )}
      {portfolios.error && (
        <div className="error" role="alert">
          {portfolios.error}{" "}
          <button
            className="secondary"
            onClick={() => setRevision((r) => r + 1)}
          >
            Retry
          </button>
        </div>
      )}
      {portfolios.loading ? (
        <p role="status">Loading workspace…</p>
      ) : active ? (
        <PortfolioContext
          key={active.id}
          portfolio={active}
          selected={
            accountSelection?.portfolioId === active.id
              ? accountSelection.value
              : ""
          }
          onSelected={(value) =>
            setAccountSelection({ portfolioId: active.id, value })
          }
          onFeedback={setFeedback}
        />
      ) : (
        !portfolios.error && (
          <section className="empty">
            <h2>Start your investment journal</h2>
            <p>
              Create a Portfolio, then add an Account to record your first
              transaction.
            </p>
            <button onClick={() => setCreating(true)}>
              Create your first Portfolio
            </button>
          </section>
        )
      )}
      {creating && (
        <EntityDialog
          kind="Portfolio"
          portfolioId={null}
          onClose={() => setCreating(false)}
          onCreated={(entity) => {
            setSelected(String(entity.id));
            setAccountSelection(null);
            setRevision((r) => r + 1);
            setCreating(false);
            setFeedback("Portfolio created.");
          }}
        />
      )}
    </main>
  );
}

function PortfolioContext({
  portfolio,
  selected,
  onSelected,
  onFeedback,
}: {
  portfolio: Entity;
  selected: string;
  onSelected: (value: string) => void;
  onFeedback: (message: string) => void;
}) {
  const [revision, setRevision] = useState(0);
  const accounts = useRead<Account[]>(
    `/portfolios/${portfolio.id}/accounts`,
    revision,
  );
  const [creating, setCreating] = useState(false);
  const account =
    selected === ""
      ? accounts.data?.[0]
      : accounts.data?.find((a) => String(a.id) === selected);
  const invalid =
    selected !== "" && selected !== "summary" && !account && !accounts.loading;
  useEffect(() => {
    if (
      accounts.data &&
      selected !== "" &&
      selected !== "summary" &&
      !accounts.data.some((a) => String(a.id) === selected)
    )
      onSelected("summary");
  }, [accounts.data, selected, onSelected]);
  return (
    <>
      <section className="context account-context">
        <label>
          Account
          <select
            aria-label="Account"
            value={account ? String(account.id) : "summary"}
            disabled={accounts.loading}
            onChange={(e) => {
              onSelected(e.target.value);
              onFeedback("");
            }}
          >
            <option value="summary">Portfolio summary</option>
            {accounts.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} · #{a.id}
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary"
          disabled={accounts.loading || !!accounts.error}
          onClick={() => setCreating(true)}
        >
          Create Account
        </button>
      </section>
      {accounts.error ? (
        <div className="error" role="alert">
          {accounts.error}{" "}
          <button
            className="secondary"
            onClick={() => setRevision((r) => r + 1)}
          >
            Refresh accounts
          </button>
        </div>
      ) : accounts.loading ? (
        <p role="status">Loading accounts…</p>
      ) : (
        <>
          {invalid && (
            <p className="notice">
              The selected Account is no longer available. Portfolio summary is
              shown.
            </p>
          )}
          {!accounts.data?.length && (
            <div className="notice">
              <strong>This Portfolio has no Accounts yet.</strong>
              <p>
                Create an Account to record transactions. Portfolio summary
                remains available.
              </p>
              <button onClick={() => setCreating(true)}>
                Create your first Account
              </button>
            </div>
          )}
          <AccountWorkspace
            key={account?.id ?? "summary"}
            portfolio={portfolio}
            account={account}
            onFeedback={onFeedback}
          />
        </>
      )}
      {creating && (
        <EntityDialog
          kind="Account"
          portfolioId={portfolio.id}
          onClose={() => setCreating(false)}
          onCreated={(entity) => {
            onSelected(String(entity.id));
            setRevision((r) => r + 1);
            setCreating(false);
            onFeedback("Account created.");
          }}
        />
      )}
    </>
  );
}

function AccountWorkspace({
  portfolio,
  account,
  onFeedback,
}: {
  portfolio: Entity;
  account?: Account;
  onFeedback: (message: string) => void;
}) {
  const [tab, setTab] = useState("Holdings");
  const [asOf, setAsOf] = useState(localDate);
  const [revision, setRevision] = useState(0);
  const [recording, setRecording] = useState(false);
  const [correction, setCorrection] = useState<{
    transaction: Transaction;
    deleting: boolean;
  } | null>(null);
  const [instrumentRevision, setInstrumentRevision] = useState(0);
  const instruments = useRead<Entity[]>("/instruments", instrumentRevision);
  const [createdInstruments, setCreatedInstruments] = useState<Entity[]>([]);
  const metadata = [...(instruments.data ?? []), ...createdInstruments].filter(
    (i, index, all) => all.findIndex((other) => other.id === i.id) === index,
  );
  const scope = account
    ? `/accounts/${account.id}`
    : `/portfolios/${portfolio.id}`;
  const positions = useRead<Position[]>(`${scope}/positions`, revision);
  const result = useRead<Realised>(`${scope}/realised-pnl`, revision);
  const money = useRead<MoneySummary>(
    dateError(asOf) ? null : `${scope}/money-summary?as_of_date=${asOf}`,
    revision,
  );
  const history = useRead<Transaction[]>(
    account ? `${scope}/transactions` : null,
    revision,
  );
  const active =
    tab === "Holdings"
      ? positions
      : tab === "History"
        ? history
        : tab === "Money"
          ? money
          : result;
  return (
    <section className="account-workspace">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">{account ? "Account" : "Portfolio summary"}</p>
          <h2>{account?.name ?? portfolio.name}</h2>
        </div>
        {account && (
          <button
            disabled={
              positions.loading ||
              instruments.loading ||
              !!instruments.error ||
              history.loading ||
              !!history.error
            }
            onClick={() => setRecording(true)}
          >
            Record transaction
          </button>
        )}
      </div>
      <div className="toolbar">
        <div role="tablist" aria-label="Workspace views">
          {(account
            ? ["Holdings", "History", "Money", "Realised result"]
            : ["Holdings", "Money", "Realised result"]
          ).map((name) => (
            <button
              key={name}
              role="tab"
              id={`tab-${name.replaceAll(" ", "-")}`}
              aria-selected={tab === name}
              aria-controls="workspace-panel"
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ))}
        </div>
        <button
          className="secondary refresh"
          onClick={() => {
            setRevision((r) => r + 1);
            setInstrumentRevision((r) => r + 1);
          }}
          disabled={active.loading}
        >
          Refresh
        </button>
      </div>
      {instruments.error && (
        <p role="alert" className="error">
          Instrument metadata: {instruments.error}{" "}
          <button onClick={() => setInstrumentRevision((r) => r + 1)}>
            Retry
          </button>
        </p>
      )}
      <div
        role="tabpanel"
        id="workspace-panel"
        aria-labelledby={`tab-${tab.replaceAll(" ", "-")}`}
        className="panel"
        aria-busy={active.loading}
      >
        {tab === "Money" ? (
          <>
            <MoneyView
              data={money.data}
              asOf={asOf}
              setAsOf={setAsOf}
              account={!!account}
              noHistory={history.data?.length === 0}
              onRecord={
                account &&
                !history.loading &&
                !history.error &&
                !instruments.loading &&
                !instruments.error
                  ? () => setRecording(true)
                  : undefined
              }
            />
            {money.loading && <p role="status">Loading Money…</p>}
            {money.error && (
              <p className="error" role="alert">
                {money.error} Use Refresh to retry.
              </p>
            )}
          </>
        ) : active.loading ? (
          <p role="status">Loading {tab.toLowerCase()}…</p>
        ) : active.error ? (
          <p className="error" role="alert">
            {active.error} Use Refresh to retry or reselect the Portfolio /
            Account.
          </p>
        ) : tab === "Holdings" && positions.data ? (
          <Holdings positions={positions.data} account={!!account} />
        ) : tab === "History" && history.data ? (
          <History
            transactions={history.data}
            instruments={metadata}
            onEdit={
              instruments.loading || instruments.error
                ? undefined
                : (transaction) =>
                    setCorrection({ transaction, deleting: false })
            }
            onDelete={(transaction) =>
              setCorrection({ transaction, deleting: true })
            }
          />
        ) : (
          result.data && <RealisedResult result={result.data} />
        )}
      </div>
      {recording && account && (
        <TransactionDialog
          accountId={account.id}
          positions={positions.data ?? []}
          instruments={metadata}
          history={history.data ?? []}
          onClose={() => setRecording(false)}
          onInstrumentCreated={(entity) => {
            setCreatedInstruments((old) => [...old, entity]);
            setInstrumentRevision((r) => r + 1);
          }}
          onRecorded={() => {
            setRecording(false);
            setRevision((r) => r + 1);
            onFeedback("Transaction recorded.");
          }}
        />
      )}
      {correction && account && (
        <CorrectionDialog
          transaction={correction.transaction}
          deleting={correction.deleting}
          instruments={metadata}
          history={history.data ?? []}
          onClose={() => setCorrection(null)}
          onCorrected={() => {
            setCorrection(null);
            setRevision((r) => r + 1);
            onFeedback(
              correction.deleting
                ? "Transaction deleted."
                : "Transaction updated.",
            );
          }}
        />
      )}
    </section>
  );
}
