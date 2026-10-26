import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CollectionStatus, DataEmptyState } from "./collection-notice";
import type { IngestionStatus } from "@/lib/api";

const status = (overrides: Partial<IngestionStatus> = {}): IngestionStatus => ({
  status: "not_started", source: "bluesky", posts_stored: 0, posts_per_minute: null,
  last_event_at: null, last_persisted_at: null, last_status_update_at: null,
  collection_started_at: null, last_seq: null, cursor_expired: false, ...overrides,
});

describe("collection status presentation", () => {
  it("does not describe failed persistence as a live connection", () => {
    const markup = renderToStaticMarkup(<CollectionStatus data={status({ status: "error", health: "persistence_failure", posts_stored: 123 })} />);
    expect(markup).toContain("Collection needs attention");
    expect(markup).toContain("operator review");
    expect(markup).not.toContain("is-live");
    expect(markup).not.toContain("Waiting to reconnect");
  });

  it("keeps a fresh socket neutral until persistence succeeds", () => {
    const markup = renderToStaticMarkup(<CollectionStatus data={status({ status: "collecting", health: "processing", worker_fresh: true })} />);
    expect(markup).toContain("Processing Bluesky events");
    expect(markup).not.toContain("is-live");
  });
  it("shows actual stored values and active wording only for a live status", () => {
    const markup = renderToStaticMarkup(<CollectionStatus data={status({
      status: "collecting", posts_stored: 124, posts_per_minute: 8,
    })} />);
    expect(markup).toContain("Collecting Bluesky posts");
    expect(markup).toContain("124");
    expect(markup).toContain("8");
    expect(markup).toContain("is-live");
  });

  it("does not use the live indicator before collection begins", () => {
    const markup = renderToStaticMarkup(<CollectionStatus data={status()} />);
    expect(markup).toContain("Collection not started");
    expect(markup).not.toContain("is-live");
  });

  it("explains cursor expiry without implying automatic recovery", () => {
    const markup = renderToStaticMarkup(<CollectionStatus data={status({
      status: "interrupted", cursor_expired: true,
    })} />);
    expect(markup).toContain("replay window has expired");
    expect(markup).toContain("operator needs to review recovery");
    expect(renderToStaticMarkup(<DataEmptyState state="reconnecting" />)).toContain("not zero activity");
  });
});
