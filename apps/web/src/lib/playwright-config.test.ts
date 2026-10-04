// @vitest-environment node
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

test("plain E2E uses isolated Web/API defaults and never reuses a server", async () => {
  vi.stubEnv("WEB_PORT", undefined);
  vi.stubEnv("API_URL", undefined);
  vi.stubEnv("CI", undefined);
  const { default: config } = await import("../../playwright.config");

  expect(config.use?.baseURL).toBe("http://127.0.0.1:3001");
  expect(config.webServer).toMatchObject({
    command: "pnpm dev --hostname 127.0.0.1 --port 3001",
    url: "http://127.0.0.1:3001",
    env: { API_URL: "http://127.0.0.1:8001" },
    reuseExistingServer: false,
  });
});

test("explicit isolated endpoints are passed to a fresh E2E Web server", async () => {
  vi.stubEnv("WEB_PORT", "3101");
  vi.stubEnv("API_URL", "http://127.0.0.1:8101");
  const { default: config } = await import("../../playwright.config");

  expect(config.use?.baseURL).toBe("http://127.0.0.1:3101");
  expect(config.webServer).toMatchObject({
    command: "pnpm dev --hostname 127.0.0.1 --port 3101",
    env: { API_URL: "http://127.0.0.1:8101" },
    reuseExistingServer: false,
  });
});
