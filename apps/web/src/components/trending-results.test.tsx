import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { TrendingResults } from "./trending-results";
import type { Trend, TrendPage } from "@/lib/trends";

describe("persisted trend results", () => {
  it("distinguishes a stopped trend processor from data collection", () => {
    const data: TrendPage = { items: [], category: "popular", window_minutes: 5, language: "all", limit: 3, offset: 0, has_more: false, status: "stopped", message: "Ingestion status is reported separately.", last_calculated_at: null };
    const markup = renderToStaticMarkup(<TrendingResults data={data} />);
    expect(markup).toContain("Trend processing is stopped.");
    expect(markup).not.toContain("Collecting more conversation data");
  });
  it("explains an unavailable service without inserting sample trends", () => {
    const markup = renderToStaticMarkup(<TrendingResults data={null} />);
    expect(markup).toContain("temporarily unavailable");
    expect(markup).not.toContain("trend-card-rank");
  });

  it("shows supplied counts and new activity without inventing a growth percentage", () => {
    const trend: Trend = { topic_id: "a".repeat(64), label: "#caturday", topic_type: "hashtag", rank: 1, window_minutes: 5, language: "all", current_activity: 10, previous_activity: 0, unique_contributors: 8, growth_percent: null, growth_state: "new_activity", velocity: 2, acceleration: 0.4, momentum_score: 55, trend_status: "Emerging", coverage_status: "complete_observed_window", coverage_fraction: 1, comparison_valid: true, as_of: "2026-01-01T12:00:00Z", calculated_at: "2026-01-01T12:01:00Z", history: [] };
    const data: TrendPage = { items: [trend], category: "emerging", window_minutes: 5, language: "all", limit: 3, offset: 0, has_more: false, status: "ready", message: "", last_calculated_at: trend.calculated_at };
    const markup = renderToStaticMarkup(<TrendingResults data={data} />);
    expect(markup).toContain("New activity · no percentage baseline");
    expect(markup).toContain("8 unique contributors");
    expect(markup).toContain("caturday.webp");
    expect(markup).toContain("/explore?");
    expect(markup).not.toContain("0.0%");
  });
});
