import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://127.0.0.1:3000", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium", launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } } },
  ],
  webServer: { command: "npm run dev", url: "http://127.0.0.1:3000", reuseExistingServer: !process.env.CI, timeout: 120000 },
});
