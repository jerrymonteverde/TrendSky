export type CollectionState = "not_started" | "unavailable";

export async function getCollectionState(): Promise<CollectionState> {
  try {
    const origin = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${origin}/api/v1/analytics/summary`, {
      cache: "no-store", signal: AbortSignal.timeout(2500),
    });
    if (!response.ok) return "unavailable";
    const data: unknown = await response.json();
    if (typeof data === "object" && data !== null && "collection_status" in data && data.collection_status === "not_started") {
      return "not_started";
    }
    return "unavailable";
  } catch {
    return "unavailable";
  }
}
