// Deterministic synthetic HTTP fixtures for browser tests only. Never a product data source.
import { createServer } from "node:http";

const now = new Date();
const iso = now.toISOString();
const id = "a".repeat(64);
const trend = (category = "popular", window = 5, language = "all") => {
  const current = category === "rising" ? 18 : 12;
  const previous = category === "emerging" ? 0 : 12;
  const g = Math.max(0, (current - previous) / (current + previous + 1));
  const momentum = 100 * (0.25 * current / (current + 20) + 0.25 * 0.5 + 0.5 * g);
  const history = Array.from({ length: 8 }, (_, index) => ({
    start: new Date(+now - (8 - index) * window * 60000).toISOString(),
    end: new Date(+now - (7 - index) * window * 60000).toISOString(),
    posts: index === 7 ? current : previous, observed_posts: index === 7 ? current : previous,
    coverage_status: "complete_observed_window", coverage_fraction: 1,
  }));
  return {
  topic_id: id, label: category === "rising" ? "#rocket" : category === "emerging" ? "#newtopic" : "#caturday",
  topic_type: "hashtag", rank: 1, window_minutes: window, language, current_activity: current,
  previous_activity: previous, unique_contributors: 10,
  growth_percent: category === "emerging" ? null : category === "rising" ? 50 : 0,
  growth_state: category === "emerging" ? "new_activity" : "comparable",
  velocity: current / window, acceleration: (current - previous) / (window * window), momentum_score: momentum,
  trend_status: category === "rising" ? "Rising" : category === "emerging" ? "Emerging" : "Stable",
  coverage_status: "complete_observed_window", coverage_fraction: 1, comparison_valid: true,
  as_of: iso, calculated_at: iso, history,
  };
};

createServer((request, response) => {
  const url = new URL(request.url, "http://localhost");
  response.setHeader("Content-Type", "application/json");
  let body;
  if (url.pathname === "/api/v1/live") body = { status: "ok" };
  else if (url.pathname === "/api/v1/ingestion/status") body = { status: "collecting", source: "bluesky", posts_stored: 120, posts_per_minute: 12, last_event_at: iso, last_persisted_at: iso, last_status_update_at: iso, collection_started_at: iso, last_seq: 12, cursor_expired: false };
  else if (url.pathname === "/api/v1/analytics/summary") body = { collection_status: "collecting" };
  else if (url.pathname === "/api/v1/trending") {
    const category = url.searchParams.get("category") || "popular";
    const language = url.searchParams.get("language") || "all";
    const window = Number(url.searchParams.get("window") || 5);
    if (language === "other") { response.statusCode = 503; body = { detail: "Synthetic unavailable service" }; }
    else body = { items: language === "unknown" ? [] : [trend(category, window, language)], category, window_minutes: window, language, limit: 12, offset: 0, has_more: false, status: language === "unknown" ? "collecting_history" : "ready", message: "Not enough historical observations to calculate growth.", last_calculated_at: iso };
  } else if (url.pathname === "/api/v1/topics/search") body = { items: [] };
  else if (url.pathname.startsWith(`/api/v1/topics/${id}`)) body = { topic_id: id, label: "#caturday", topic_type: "hashtag", status: "complete_observed_window", activity: trend() };
  else { response.statusCode = 404; body = { detail: "Synthetic fixture route missing" }; }
  response.end(JSON.stringify(body));
}).listen(3181, "127.0.0.1");
