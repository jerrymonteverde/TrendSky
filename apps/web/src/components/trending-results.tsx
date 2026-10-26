import { TrendCard } from "@/components/trend-card";
import { completeSeries, topicIllustration, topicLink, windowLabel, type TrendPage } from "@/lib/trends";

export function TrendingResults({ data }: { data: TrendPage | null }) {
  if (!data || data.items.length === 0) {
    const message = data?.message || "Trending results are temporarily unavailable.";
    const title = !data ? "Trending results are taking a moment." : ["not_started", "stopped", "disabled"].includes(data.status) ? "Trend processing is stopped." : ["error", "stale"].includes(data.status) ? "Trending results need a fresh calculation." : data.status === "catching_up" ? "Processing the conversation backlog." : "Collecting more conversation data.";
    return <div className="data-empty"><p className="empty-kicker">OBSERVATIONS BEFORE CONCLUSIONS</p><h3>{title}</h3><p className="empty-description">{message}</p><p className="trend-card-context">Growth requires comparable collection windows. Missing coverage is never counted as zero activity.</p></div>;
  }
  return <><div className="trend-card-grid">{data.items.map((trend) => <TrendCard key={trend.topic_id} trend={{ rank: trend.rank, topic: trend.label, category: trend.topic_type, observedPosts: trend.current_activity, growthPercent: trend.growth_percent, activitySeries: completeSeries(trend.history), illustration: topicIllustration(trend.label), href: topicLink(trend), status: trend.trend_status, contributors: trend.unique_contributors, updatedAt: trend.calculated_at, coverage: trend.coverage_status, growthState: trend.growth_state }} />)}</div><p className="trend-results-note">{windowLabel(data.window_minutes)} of observed activity, ending {data.items[0].as_of.replace("T", " ").slice(0, 16)} UTC. Matching posts may overlap across topics. Counts describe retained public Bluesky observations.</p></>;
}
