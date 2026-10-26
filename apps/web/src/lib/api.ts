export type CollectionState = "not_started" | "connecting" | "collecting" | "reconnecting" | "interrupted" | "error" | "unavailable";

export type IngestionStatus = {
  status: CollectionState;
  source: string;
  posts_stored: number;
  posts_per_minute: number | null;
  last_event_at: string | null;
  last_persisted_at: string | null;
  last_status_update_at: string | null;
  collection_started_at: string | null;
  last_seq: number | null;
  cursor_expired: boolean;
  health?: "connected" | "connecting" | "reconnecting" | "processing" | "persistence_failure" | "cursor_expired" | "stopped";
  worker_fresh?: boolean;
  persistence_fault?: { batch_id: string; blocked: boolean; category: string; phase: string } | null;
};

const emptyStatus = (status: CollectionState): IngestionStatus => ({
  status, source: "bluesky", posts_stored: 0, posts_per_minute: null,
  last_event_at: null, last_persisted_at: null, last_status_update_at: null,
  collection_started_at: null, last_seq: null, cursor_expired: false,
});

export async function getIngestionStatus(): Promise<IngestionStatus> {
  try {
    const origin = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${origin}/api/v1/ingestion/status`, {
      cache: "no-store", signal: AbortSignal.timeout(2500),
    });
    if (!response.ok) return emptyStatus("unavailable");
    const data: unknown = await response.json();
    if (typeof data !== "object" || data === null || !("status" in data)) return emptyStatus("unavailable");
    const value = data as Partial<IngestionStatus>;
    if (!(["not_started", "connecting", "collecting", "reconnecting", "interrupted", "error"] as string[]).includes(value.status ?? "")) return emptyStatus("unavailable");
    return { ...emptyStatus(value.status as CollectionState), ...value };
  } catch {
    return emptyStatus("unavailable");
  }
}

export async function getCollectionState(): Promise<CollectionState> {
  try {
    const origin = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${origin}/api/v1/analytics/summary`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
    if (!response.ok) return "unavailable";
    const data: unknown = await response.json();
    if (typeof data === "object" && data !== null && "collection_status" in data) {
      const state = data.collection_status;
      if (["not_started", "connecting", "collecting", "reconnecting", "interrupted", "error"].includes(String(state))) return state as CollectionState;
    }
    return "unavailable";
  } catch {
    return "unavailable";
  }
}
