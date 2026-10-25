import { afterEach, describe, expect, it, vi } from "vitest";
import { getCollectionState } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("collection status transport", () => {
  it("reads the implemented API contract", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ collection_status: "not_started" })));
    vi.stubGlobal("fetch", fetcher);
    expect(await getCollectionState()).toBe("not_started");
    expect(fetcher.mock.calls[0][0]).toContain("/api/v1/analytics/summary");
    expect(fetcher.mock.calls[0][1].cache).toBe("no-store");
  });
  it.each([503, 429])("treats HTTP %s as unavailable", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status })));
    expect(await getCollectionState()).toBe("unavailable");
  });
  it("does not claim collection is stopped for an unknown payload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
    expect(await getCollectionState()).toBe("unavailable");
  });
  it("handles network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect(await getCollectionState()).toBe("unavailable");
  });
});
