import type { TopicDetail } from "@/lib/trends";
import { windowLabel } from "@/lib/trends";

export function TopicSummary({ topic }: { topic: TopicDetail }) {
  const activity = topic.activity;
  if (!activity) return <div className="data-empty"><h3>More observations are needed for {topic.label}.</h3><p>The topic was discovered, but a supported activity window is not available yet.</p></div>;
  return <div className="topic-summary"><div className="section-heading"><h3>{topic.label}</h3><span className="pill">{windowLabel(activity.window_minutes)} · {activity.trend_status}</span></div>
    <dl className="topic-metrics"><div><dt>Observed posts</dt><dd>{activity.current_activity.toLocaleString()}</dd></div><div><dt>Unique contributors</dt><dd>{activity.unique_contributors.toLocaleString()}</dd></div><div><dt>Growth</dt><dd>{activity.growth_percent === null ? activity.growth_state === "new_activity" ? "New activity" : "Insufficient baseline" : `${activity.growth_percent.toFixed(1)}%`}</dd></div><div><dt>Collection coverage</dt><dd>{(activity.coverage_fraction * 100).toFixed(1)}% · {activity.coverage_status.replaceAll("_", " ")}</dd></div></dl>
    <p className="trend-results-note">Recent windows use UTC boundaries. A dash marks incomplete coverage; it does not mean no posts were observed.</p>
    <div className="topic-history"><table><caption>Recent observed activity, {windowLabel(activity.window_minutes)} per window</caption><thead><tr><th scope="col">Window end (UTC)</th><th scope="col">Posts</th><th scope="col">Coverage</th></tr></thead><tbody>{activity.history.map((point) => <tr key={point.end}><th scope="row"><time dateTime={point.end}>{point.end.replace("T", " ").slice(0, 16)}</time></th><td>{point.posts === null ? "—" : point.posts.toLocaleString()}</td><td>{point.coverage_status.replaceAll("_", " ")}</td></tr>)}</tbody></table></div>
    <p className="trend-results-note">Calculated <time dateTime={activity.calculated_at}>{activity.calculated_at.replace("T", " ").slice(0, 16)} UTC</time>. These are descriptive observations, not predictions.</p>
  </div>;
}
