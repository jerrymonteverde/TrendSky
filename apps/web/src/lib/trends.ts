export const trendWindows = [5, 15, 60, 360, 1440] as const;
export type TrendCategory = "popular" | "rising" | "emerging";
export type TrendHistory = { start: string; end: string; posts: number | null; observed_posts: number; coverage_status: string; coverage_fraction: number };
export type Trend = {
  topic_id: string; label: string; topic_type: string; rank: number;
  window_minutes: number; language: string; current_activity: number; previous_activity: number | null;
  unique_contributors: number; growth_percent: number | null; growth_state: string;
  velocity: number | null; acceleration: number | null; momentum_score: number;
  trend_status: string; coverage_status: string; coverage_fraction: number;
  comparison_valid: boolean; as_of: string; calculated_at: string; history: TrendHistory[];
};
export type TrendPage = { items: Trend[]; category: string; window_minutes: number; language: string; limit: number; offset: number; has_more: boolean; status: string; message: string; last_calculated_at: string | null };
export type TopicDetail = { topic_id: string; label: string; topic_type: string; status: string; activity: Trend | null };
export type TopicMatch = { topic_id: string; label: string; topic_type: string };

async function apiData<T>(path: string): Promise<T | null> {
  try {
    const origin = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${origin}/api/v1/${path}`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
    if (!response.ok) return null;
    return await response.json() as T;
  } catch {
    return null;
  }
}

export async function getTrends(category: TrendCategory = "popular", window = 5, language = "all", limit = 20, offset = 0): Promise<TrendPage | null> {
  const query = new URLSearchParams({ category, window: String(window), language, limit: String(limit), offset: String(offset) });
  const data = await apiData<TrendPage>(`trending?${query}`);
  return data && Array.isArray(data.items) ? data : null;
}

export function getTopic(topicId: string, window = 5, language = "all"): Promise<TopicDetail | null> {
  if (!/^[0-9a-f]{64}$/.test(topicId)) return Promise.resolve(null);
  return apiData<TopicDetail>(`topics/${topicId}?${new URLSearchParams({ window: String(window), language })}`);
}

export async function searchTopics(query: string): Promise<TopicMatch[]> {
  if (!query) return [];
  const data = await apiData<{ items: TopicMatch[] }>(`topics/search?${new URLSearchParams({ q: query, limit: "10" })}`);
  return data && Array.isArray(data.items) ? data.items : [];
}

// Exact reviewed aliases to existing editorial art. Artwork never determines ranking.
const artwork: Record<string, string> = {
  caturday: "caturday", gaming: "gaming", "video games": "gaming", "video juegos": "gaming",
  "climate change": "climate-change", climatechange: "climate-change", "cambio climático": "climate-change",
  mexico: "mexico", "méxico": "mexico", productivity: "productivity", books: "books",
  technology: "technology", tech: "technology", science: "science", ciencia: "science",
  music: "music", "música": "music", art: "art", arte: "art", sports: "sports", travel: "travel",
};

export function topicIllustration(label: string): { src: string; alt: string } | undefined {
  const key = label.normalize("NFKC").toLowerCase().replace(/^#/, "");
  const asset = artwork[key];
  return asset ? { src: `/images/topics/${asset}.webp`, alt: "" } : undefined;
}

export function topicLink(trend: Pick<Trend, "topic_id" | "label" | "window_minutes" | "language">): string {
  return `/explore?${new URLSearchParams({ q: trend.label, topic: trend.topic_id, window: String(trend.window_minutes), language: trend.language })}`;
}

export function completeSeries(history: TrendHistory[]): number[] | undefined {
  const values = history.map((point) => point.posts);
  return values.length >= 2 && values.every((value): value is number => value !== null && Number.isFinite(value)) ? values : undefined;
}

export function windowLabel(minutes: number): string {
  return minutes < 60 ? `${minutes} minutes` : minutes < 1440 ? `${minutes / 60} hour${minutes === 60 ? "" : "s"}` : "24 hours";
}
