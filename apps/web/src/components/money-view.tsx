import { dateError, Field } from "./entry-dialogs";

const groups = [
  [
    "External flows",
    [
      ["deposits", "Deposits"],
      ["withdrawals", "Withdrawals"],
    ],
  ],
  [
    "Trading cash",
    [
      ["buy_trade_cash_outflow", "Buy cash outflow"],
      ["sell_trade_cash_inflow", "Sell cash inflow"],
    ],
  ],
  [
    "Investment income",
    [
      ["gross_investment_income", "Gross investment income"],
      ["gross_dividend_income", "Gross dividend income"],
      ["gross_coupon_income", "Gross coupon income"],
    ],
  ],
  [
    "Fees and taxes",
    [
      ["fees_paid", "Fees paid"],
      ["taxes_paid_or_withheld", "Taxes paid or withheld"],
    ],
  ],
] as const;
const fields = [
  "cash_balance",
  ...groups.flatMap(([, metrics]) => metrics.map(([field]) => field)),
];
export type MoneySummary = {
  as_of_date: string;
  currencies: ({ currency_code: string } & Record<string, string>)[];
};

export function formatCash(value: string, currency: string) {
  if (
    typeof value !== "string" ||
    !/^(0|-?[1-9]\d*)(\.\d{1,8})?$|^-?0\.\d{1,8}$/.test(value) ||
    value === "-0" ||
    (value.includes(".") && value.endsWith("0"))
  )
    throw new Error("Invalid monetary payload.");
  const [integer, fraction] = value.replace(/^-/, "").split(".");
  return `${value.startsWith("-") ? "−" : ""}${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction ? `.${fraction}` : ""} ${currency}`;
}

export function MoneyView({
  data,
  asOf,
  setAsOf,
  account,
  noHistory,
  onRecord,
}: {
  data?: MoneySummary;
  asOf: string;
  setAsOf: (value: string) => void;
  account: boolean;
  noHistory: boolean;
  onRecord?: () => void;
}) {
  let error = "";
  try {
    if (data !== undefined) {
      if (
        !data ||
        typeof data !== "object" ||
        data.as_of_date !== asOf ||
        !Array.isArray(data.currencies)
      )
        throw new Error("Invalid Money summary.");
      const currencies = new Set<string>();
      for (const item of data.currencies) {
        if (
          !/^[A-Z]{3}$/.test(item.currency_code) ||
          currencies.has(item.currency_code)
        )
          throw new Error("Invalid Money currency.");
        currencies.add(item.currency_code);
        for (const field of fields) {
          formatCash(item[field], item.currency_code);
          if (field !== "cash_balance" && item[field].startsWith("-"))
            throw new Error("Invalid outflow/income magnitude.");
        }
      }
    }
  } catch (issue) {
    error = issue instanceof Error ? issue.message : "Invalid Money summary.";
  }
  return (
    <section>
      <h3>Money</h3>
      <Field
        label="As of date"
        name="money-as-of"
        type="date"
        value={asOf}
        onChange={setAsOf}
        error={dateError(asOf)}
      />
      {!account && (
        <p className="muted">
          Aggregated across Accounts by currency. No FX conversion or
          cross-currency total.
        </p>
      )}
      {error ? (
        <p className="error" role="alert">
          {error} Unable to display Money.
        </p>
      ) : (
        data &&
        (data.currencies.length ? (
          <div className="money-currencies">
            {data.currencies.map((item) => (
              <article className="money-currency" key={item.currency_code}>
                <h4>{item.currency_code}</h4>
                <p>Recorded cash balance</p>
                <strong className="money-balance">
                  {formatCash(item.cash_balance, item.currency_code)}
                </strong>
                <p className="muted">
                  From recorded canonical transactions through {asOf}. Not
                  broker-reported available or settled cash.
                </p>
                {groups.map(([heading, metrics]) => (
                  <section key={heading}>
                    <h5>{heading}</h5>
                    <dl>
                      {metrics.map(([field, label]) => (
                        <div key={field}>
                          <dt>{label}</dt>
                          <dd>{formatCash(item[field], item.currency_code)}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                ))}
              </article>
            ))}
          </div>
        ) : (
          <div className="empty">
            {account && noHistory ? (
              <>
                <p>No transactions yet.</p>
                {onRecord && (
                  <button onClick={onRecord}>Record transaction</button>
                )}
              </>
            ) : (
              <p>No recorded cash activity through this date.</p>
            )}
          </div>
        ))
      )}
    </section>
  );
}
