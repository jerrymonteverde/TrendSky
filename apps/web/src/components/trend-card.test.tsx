import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { TrendCard } from "./trend-card";

describe("TrendCard", () => {
  it("shows a designed empty card without manufacturing activity metrics", () => {
    const html = renderToStaticMarkup(<TrendCard trend={{ rank: 1, topic: "Climate conversations" }} />);
    expect(html).toContain("#01");
    expect(html).toContain("Climate conversations");
    expect(html).toContain("Activity metrics will appear when measured.");
    expect(html).not.toContain("0 posts");
    expect(html).not.toContain("0.0%");
  });

  it("renders supplied observed values and a labelled miniature activity series", () => {
    const html = renderToStaticMarkup(<TrendCard trend={{ rank: 2, topic: "Studio arts", category: "Culture", observedPosts: 1234, growthPercent: 13.5, activitySeries: [2, 4, 8] }} />);
    expect(html).toContain("1,234");
    expect(html).toContain("+13.5%");
    expect(html).toContain("Culture");
    expect(html).toContain("Observed activity series for Studio arts");
  });

  it("does not chart invalid series values", () => {
    const html = renderToStaticMarkup(<TrendCard trend={{ rank: 3, topic: "Ideas", activitySeries: [2, Number.NaN, 4] }} />);
    expect(html).not.toContain("role=\"img\"");
  });
});
