import Image from "next/image";
import Link from "next/link";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

export type TrendCardData = {
  rank: number;
  topic: string;
  category?: string;
  observedPosts?: number | null;
  growthPercent?: number | null;
  activitySeries?: readonly number[];
  illustration?: { src: string; alt: string };
  href?: string;
  status?: string;
  contributors?: number;
  updatedAt?: string;
  coverage?: string;
  growthState?: string;
};

function makeSparkPath(values: readonly number[]): string | null {
  if (values.length < 2 || values.some((value) => !Number.isFinite(value) || value < 0)) return null;
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  return values.map((value, index) => {
    const x = (index / (values.length - 1)) * 100;
    const y = 29 - ((value - low) / span) * 23;
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
}

export function TrendCard({ trend }: { trend: TrendCardData }) {
  const sparkPath = trend.activitySeries ? makeSparkPath(trend.activitySeries) : null;
  const activityAvailable = typeof trend.observedPosts === "number" && Number.isFinite(trend.observedPosts) && trend.observedPosts >= 0;
  const growthAvailable = typeof trend.growthPercent === "number" && Number.isFinite(trend.growthPercent);
  const growth = trend.growthPercent ?? 0;

  return <article className="trend-card" aria-label={`Rank ${trend.rank}: ${trend.topic}`}>
    {trend.illustration && <div className="trend-card-illustration"><Image src={trend.illustration.src} alt={trend.illustration.alt} fill sizes="(max-width: 700px) 92vw, (max-width: 1000px) 46vw, 30vw" /></div>}
    <div className="trend-card-topline"><span className="trend-card-rank">#{trend.rank.toString().padStart(2, "0")}</span>{trend.category && <span className="trend-card-category">{trend.category}</span>}</div>
    <h3>{trend.href ? <Link href={trend.href}>{trend.topic}</Link> : trend.topic}</h3>
    {trend.status && <p className="trend-card-status">{trend.status}</p>}
    {activityAvailable || growthAvailable ? <div className="trend-card-metrics">
      <div><span className="trend-card-metric-label">OBSERVED POSTS</span><span className="trend-card-metric-value">{activityAvailable ? trend.observedPosts!.toLocaleString() : "—"}</span></div>
      {growthAvailable && <span className={`trend-card-growth ${growth < 0 ? "negative" : growth > 0 ? "positive" : "steady"}`}>{growth < 0 ? <ArrowDownRight size={14} aria-hidden="true" /> : growth > 0 ? <ArrowUpRight size={14} aria-hidden="true" /> : null}<span>{growth > 0 ? "+" : ""}{growth.toFixed(1)}%</span></span>}
    </div> : <p className="trend-card-no-data">Activity metrics will appear when measured.</p>}
    {!growthAvailable && trend.growthState && <p className="trend-card-no-data">{trend.growthState === "new_activity" ? "New activity · no percentage baseline" : "Growth needs more verified history"}</p>}
    {typeof trend.contributors === "number" && <p className="trend-card-context">{trend.contributors.toLocaleString()} unique contributors</p>}
    {sparkPath && <svg className="trend-card-sparkline" viewBox="0 0 100 36" preserveAspectRatio="none" role="img" aria-label={`Observed activity series for ${trend.topic}`}><path d={sparkPath} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" /></svg>}
    {trend.coverage && <p className="trend-card-context">{trend.coverage === "complete_observed_window" ? "Observed window covered" : trend.coverage === "insufficient_history" ? "Partial history" : "Partial collection coverage"}</p>}
    {trend.updatedAt && <p className="trend-card-updated">Calculated <time dateTime={trend.updatedAt}>{new Date(trend.updatedAt).toLocaleTimeString("en", { timeZone: "UTC", hour: "2-digit", minute: "2-digit" })} UTC</time></p>}
  </article>;
}
