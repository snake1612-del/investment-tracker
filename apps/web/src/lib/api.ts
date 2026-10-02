import type { MoneyWire } from "./exact-money";

export type Entity = { id: number; name: string };
export type Portfolio = Entity & { base_currency: string };
export type Account = Entity & { portfolio_id: number };
export type Position = {
  instrument_id: number;
  instrument_name: string;
  quantity: string;
};
export type Transaction = {
  id: number;
  account_id: number;
  instrument_id: number | null;
  type: string;
  effective_date: string;
  settlement_date: string | null;
  currency_code: string;
  quantity: string | null;
  price: string | null;
  cash_amount: string;
};
export type Unresolved = {
  reason: "CURRENCY_MISMATCH" | "MISSING_ACQUISITION_BASIS";
  account_id: number;
  sell_transaction_id: number;
  instrument_id: number;
  instrument_name: string;
  effective_date: string;
  quantity: string;
  allocated_proceeds: MoneyWire;
  removed_basis?: MoneyWire;
};
export type Realised = {
  metric: "GROSS_TRADE_CASH_REALISED_PNL";
  resolved_pnl_by_currency: MoneyWire[];
  unresolved_components: Unresolved[];
  is_fully_resolved: boolean;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  body?: object,
  signal?: AbortSignal,
  method?: "PUT" | "DELETE",
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: method ?? (body ? "POST" : "GET"),
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(
      "Unable to reach the server. Check that the API is running and retry.",
      0,
    );
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const fields: Record<string, string> = {};
    if (Array.isArray(payload?.detail)) {
      for (const item of payload.detail)
        fields[String(item.loc?.at(-1))] = item.msg;
    }
    throw new ApiError(
      typeof payload?.detail === "string"
        ? payload.detail
        : response.status === 404
          ? "This Portfolio or Account no longer exists. Refresh the selection."
          : response.status === 422
            ? "Please check the entered fields."
            : "Server error. Please retry.",
      response.status,
      fields,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
