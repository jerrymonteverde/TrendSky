import { expect, test } from "@playwright/test";

test("homepage, font, empty state and responsive layout", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Discover what’s rising." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Trending Right Now" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText(/Collection (not started|status unavailable)/);
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => getComputedStyle(document.body).fontFamily)).toContain("ubuntu");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("keyboard search preserves the topic in a shareable URL", async ({ page }) => {
  await page.goto("/");
  const input = page.getByRole("searchbox").or(page.getByRole("textbox", { name: "Explore a topic, keyword or hashtag" }));
  const query = '#ciencia "energía solar"';
  await input.fill(query);
  await input.press("Enter");
  await expect(page).toHaveURL(/\/explore\?q=/);
  expect(new URL(page.url()).searchParams.get("q")).toBe(query);
  await expect(page.getByRole("heading", { name: query, exact: true })).toBeVisible();
  await expect(page.getByLabel("Time range")).toBeDisabled();
  await page.reload();
  await expect(page.getByRole("textbox")).toHaveValue(query);
});

test("blank search explains the required input", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore topic" }).click();
  await expect(page.getByRole("search").getByRole("alert")).toContainText("Enter a topic");
  await expect(page).toHaveURL("/");
});

test("theme is light by default and persists after navigation and reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveClass(/light/);
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await expect(page.locator("html")).toHaveClass(/light/);
});

test("all navigation routes work with touch or mouse", async ({ page }, testInfo) => {
  await page.goto("/");
  for (const [label, path] of [["Explore", "/explore"], ["Trending Now", "/trending"], ["Predictions", "/predictions"], ["About", "/about"]]) {
    if (testInfo.project.name === "mobile") await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: label, exact: true }).click();
    await expect(page).toHaveURL(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.getByRole("link", { name: "TrendSky home" }).click();
  await expect(page).toHaveURL("/");
});

test("prediction state never invents a forecast", async ({ page }) => {
  await page.goto("/predictions");
  await expect(page.getByText("Models not available")).toBeVisible();
  await expect(page.getByText("No models have been trained or evaluated.", { exact: false })).toBeVisible();
});

test("unknown routes return a useful 404", async ({ page }) => {
  const response = await page.goto("/missing-page");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("link", { name: "Return to TrendSky" })).toBeVisible();
});
