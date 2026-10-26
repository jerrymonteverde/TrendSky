import type { Metadata } from "next";
import Link from "next/link";
import { CollectionStatus } from "@/components/collection-notice";
import { CollectionRefresh } from "@/components/collection-refresh";
import { TrendingResults } from "@/components/trending-results";
import { getIngestionStatus } from "@/lib/api";
import { getTrends, trendWindows, windowLabel, type TrendCategory } from "@/lib/trends";

export const metadata: Metadata = { title: "Trending Now" };
export const dynamic = "force-dynamic";
const categories = [{ value: "popular", label: "Popular Now" }, { value: "rising", label: "Rising Fast" }, { value: "emerging", label: "Emerging" }] as const;

export default async function Trending({ searchParams }: { searchParams: Promise<{ category?: string; window?: string; language?: string; offset?: string }> }) {
  const params = await searchParams;
  const category: TrendCategory = params.category === "rising" || params.category === "emerging" ? params.category : "popular";
  const window = trendWindows.find((value) => value === Number(params.window)) || 5;
  const language = ["en", "es", "unknown", "other"].includes(params.language || "") ? params.language! : "all";
  const offsetValue = Number(params.offset || 0);
  const offset = Number.isInteger(offsetValue) && offsetValue >= 0 && offsetValue <= 10000 ? offsetValue : 0;
  const [collection, trends] = await Promise.all([getIngestionStatus(), getTrends(category, window, language, 12, offset)]);
  const rankingUrl = (newCategory: string, newOffset = 0) => `/trending?${new URLSearchParams({ category: newCategory, window: String(window), language, offset: String(newOffset) })}`;
  return <div className="shell interior trending-page"><div className="eyebrow">WHAT’S GATHERING MOMENTUM</div><h1>Trending Now</h1><p className="page-intro">Real observations. Clear signals. A little more context.</p>
    <CollectionRefresh /><CollectionStatus data={collection} />
    <section className="trend-discovery" aria-labelledby="ranking-title"><div className="trend-discovery-head"><div><span className="eyebrow">THE SIGNAL, WITH THE CONTEXT</span><h2 id="ranking-title">Conversations in focus</h2></div></div>
      <nav className="trend-tabs" aria-label="Trend rankings">{categories.map((entry) => <Link key={entry.value} href={rankingUrl(entry.value)} aria-current={category === entry.value ? "page" : undefined}>{entry.label}</Link>)}</nav>
      <form method="get" action="/trending" className="trend-filters"><input type="hidden" name="category" value={category} /><label>Activity window<select name="window" defaultValue={window}>{trendWindows.map((value) => <option key={value} value={value}>{windowLabel(value)}</option>)}</select></label><label>Declared language<select name="language" defaultValue={language}><option value="all">All languages</option><option value="en">English</option><option value="es">Spanish</option><option value="unknown">Unknown language</option><option value="other">Other languages</option></select></label><button className="quiet-action" type="submit">Apply filters</button></form>
      <p className="trend-results-note">{category === "popular" ? "Ranked by contributor-capped activity and independent participation." : category === "rising" ? "Growth must exceed the configured threshold across two covered windows." : "New or unusually elevated activity must have enough independent contributors."}</p>
      <div className="trend-shelf"><TrendingResults data={trends} /></div>
      {(offset > 0 || trends?.has_more) && <nav className="trend-pagination" aria-label="Trend result pages">{offset > 0 && <Link className="text-link" href={rankingUrl(category, Math.max(0, offset - 12))}>Previous results</Link>}{trends?.has_more && <Link className="text-link" href={rankingUrl(category, offset + 12)}>More conversations →</Link>}</nav>}
    </section>
    <aside className="home-disclaimer"><p>Growth is unavailable when collection windows are incomplete. Topic mentions can overlap. Declared language metadata can be missing or inaccurate.</p><Link href="/about#coverage">About coverage →</Link></aside>
  </div>;
}
