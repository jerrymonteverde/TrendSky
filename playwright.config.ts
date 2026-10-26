import { defineConfig, devices } from "@playwright/test";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3100";
const port = new URL(baseURL).port || "3100";
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium", launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } } },
  ],
  webServer: [
    { command: "node tests/e2e/api-fixture.mjs", url: "http://127.0.0.1:3181/api/v1/live", reuseExistingServer: false },
    { command: `npm run dev --workspace=@trendsky/web -- --port ${port}`, url: baseURL, env: { API_INTERNAL_URL: "http://127.0.0.1:3181" }, reuseExistingServer: false, timeout: 120000 },
  ],
});
