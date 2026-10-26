import { expect, test } from "@playwright/test";

test("ranking navigation and filters preserve the measured-data route", async ({ page }, testInfo) => {
  await page.goto("/trending");
  await expect(page.getByRole("link", { name: "Popular Now", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("article", { name: "Rank 1: #caturday" })).toBeVisible();
  await page.getByRole("link", { name: "Rising Fast", exact: true }).click();
  await expect(page).toHaveURL(/category=rising/);
  await expect(page.getByRole("article", { name: "Rank 1: #rocket" })).toBeVisible();
  await page.getByLabel("Activity window").selectOption("15");
  await page.getByLabel("Declared language").selectOption("es");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/window=15&language=es/);
  await expect(page.getByLabel("Declared language")).toHaveValue("es");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("trending.png"), fullPage: true, caret: "initial" });
});

test("topic cards open a basic observed history without changing search behavior", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("link", { name: "#caturday", exact: true }).click();
  await expect(page).toHaveURL(/\/explore\?q=%23caturday&topic=/);
  await expect(page.getByRole("heading", { name: "Recent observed activity" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Posts", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("topic-history.png"), fullPage: true, caret: "initial" });
});

test("empty and failed ranking responses explain unavailable observations", async ({ page }) => {
  await page.goto("/trending?category=rising&language=unknown");
  await expect(page.getByText("Not enough historical observations to calculate growth.")).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
  await page.goto("/trending?language=other");
  await expect(page.getByText("Trending results are temporarily unavailable.")).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
});
