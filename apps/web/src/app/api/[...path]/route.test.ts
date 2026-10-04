// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { DELETE, GET, PUT } from "./route";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

it("resolves the internal binding at request time and preserves query and precision", async () => {
  vi.stubEnv("API_URL", "http://internal-api/");
  const fetcher = vi.fn().mockResolvedValue(
    new Response('{"amount":"123456789.00000001"}', {
      headers: { "content-type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  const result = await GET(
    new Request(
      "https://preview.example/api/accounts/1/money-summary?as_of_date=2026-10-04",
    ),
  );
  expect(fetcher.mock.calls[0][0].href).toBe(
    "http://internal-api/accounts/1/money-summary?as_of_date=2026-10-04",
  );
  expect(await result.text()).toContain("123456789.00000001");
  expect(fetcher.mock.calls[0][1].cache).toBe("no-store");
});

it("forwards mutation bytes and 204 without retries", async () => {
  vi.stubEnv("API_URL", "http://api:8000");
  const fetcher = vi
    .fn()
    .mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetcher);
  const body = '{"cash_amount":"1.00000001"}';
  await PUT(
    new Request("http://localhost/api/accounts/1/transactions/2", {
      method: "PUT",
      body,
    }),
  );
  expect(new TextDecoder().decode(fetcher.mock.calls[0][1].body)).toBe(body);
  expect(
    (
      await DELETE(
        new Request("http://localhost/api/accounts/1/transactions/2", {
          method: "DELETE",
        }),
      )
    ).status,
  ).toBe(204);
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("fails closed on Vercel without a binding, never falling back to localhost", async () => {
  vi.stubEnv("VERCEL", "1");
  vi.stubEnv("API_URL", undefined);
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  expect(
    (await GET(new Request("https://preview.example/api/health"))).status,
  ).toBe(503);
  expect(fetcher).not.toHaveBeenCalled();
});

it("returns a safe gateway error without leaking upstream details", async () => {
  vi.stubEnv("API_URL", "http://internal-api");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("private upstream detail")),
  );
  const result = await GET(new Request("https://preview.example/api/health"));
  expect(result.status).toBe(502);
  expect(await result.text()).not.toContain("private");
});

it("keeps redirects same-origin without exposing private service bindings", async () => {
  vi.stubEnv("API_URL", "https://private-api.example/binding-grant/");
  const fetcher = vi.fn().mockResolvedValue(
    new Response(null, {
      status: 307,
      headers: {
        location: "https://private-api.example/binding-grant/portfolios?x=1",
      },
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  const result = await GET(
    new Request("https://preview.example/api/portfolios/"),
  );
  expect(result.headers.get("location")).toBe(
    "https://preview.example/api/portfolios?x=1",
  );
  fetcher.mockResolvedValue(
    new Response(null, {
      status: 307,
      headers: { location: "https://elsewhere.example" },
    }),
  );
  expect(
    (await GET(new Request("https://preview.example/api/portfolios/"))).status,
  ).toBe(502);
});
