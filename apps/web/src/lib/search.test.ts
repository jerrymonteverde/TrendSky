import { describe, expect, it } from "vitest";
import { exploreUrl, normalizeQuery } from "./search";

describe("topic queries", () => {
  it("preserves hashtags, Spanish and exact phrase punctuation in URLs", () => {
    const query = '#ciencia "energía solar" & clima';
    expect(new URL(exploreUrl(query), "https://trendsky.test").searchParams.get("q")).toBe(query);
  });
  it("normalizes whitespace and bounds input", () => {
    expect(normalizeQuery("  sky   blue  ")).toBe("sky blue");
    expect(normalizeQuery("x".repeat(200))).toHaveLength(120);
    expect(exploreUrl(" ")).toBe("/explore");
  });
});
