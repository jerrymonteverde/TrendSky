import { afterEach, describe, expect, it, vi } from "vitest";
import { completeSeries, getTrends, topicIllustration, topicLink } from "./trends";

afterEach(() => vi.unstubAllGlobals());

describe("measured trend transport and artwork", () => {
  it("uses server API filters and handles an unavailable endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] })));
    vi.stubGlobal("fetch", fetcher);
    expect(await getTrends("rising", 15, "es", 12)).toEqual({ items: [] });
    expect(fetcher.mock.calls[0][0]).toContain("category=rising&window=15&language=es&limit=12");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 503 })));
    expect(await getTrends()).toBeNull();
  });

  it("maps only reviewed exact topic labels and has a neutral unmatched fallback", () => {
    expect(topicIllustration("#Caturday")?.src).toContain("caturday.webp");
    expect(topicIllustration("climate change")?.src).toContain("climate-change.webp");
    expect(topicIllustration("technology scandal")).toBeUndefined();
    expect(topicIllustration("unknown topic")).toBeUndefined();
  });

  it("does not connect a sparkline across missing coverage", () => {
    const point = { start: "a", end: "b", observed_posts: 5, coverage_status: "complete_observed_window", coverage_fraction: 1 };
    expect(completeSeries([{ ...point, posts: 5 }, { ...point, posts: null }])).toBeUndefined();
    expect(completeSeries([{ ...point, posts: 5 }, { ...point, posts: 0 }])).toEqual([5, 0]);
    expect(topicLink({ topic_id: "a".repeat(64), label: "#México", window_minutes: 15, language: "es" })).toContain("q=%23M%C3%A9xico");
  });
});
