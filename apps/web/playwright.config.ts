import { defineConfig } from "@playwright/test";

const port = process.env.WEB_PORT ?? "3001";
const baseURL = `http://127.0.0.1:${port}`;
const apiURL = process.env.API_URL ?? "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "narrow", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: `pnpm dev --hostname 127.0.0.1 --port ${port}`,
    url: baseURL,
    env: { API_URL: apiURL },
    reuseExistingServer: false,
  },
});
