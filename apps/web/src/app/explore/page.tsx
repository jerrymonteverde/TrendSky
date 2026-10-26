import type { Metadata } from "next";
import { ArrowRight, Info } from "lucide-react";
import Link from "next/link";
import { SearchForm } from "@/components/search-form";
import { CollectionNotice, DataEmptyState } from "@/components/collection-notice";
import { getCollectionState } from "@/lib/api";
import { normalizeQuery } from "@/lib/search";
import { getTopic, searchTopics, topicLink, trendWindows, windowLabel } from "@/lib/trends";
import { TopicSummary } from "@/components/topic-summary";
export const metadata: Metadata = { title: "Explore" };
export const dynamic = "force-dynamic";
export default async function Explore({ searchParams }: { searchParams: Promise<{ q?: string | string[]; topic?: string; window?: string; language?: string }> }) {
  const params = await searchParams;
  const query = normalizeQuery(typeof params.q === "string" ? params.q : "");
  const state = await getCollectionState();
  const window = trendWindows.find((value) => value === Number(params.window)) || 5;
  const language = ["all", "en", "es", "unknown", "other"].includes(params.language || "") ? params.language! : "all";
  const matches = query && !params.topic ? await searchTopics(query) : [];
  const exact = matches.find((item) => item.label.normalize("NFKC").toLowerCase() === query.normalize("NFKC").toLowerCase());
  const topic = params.topic || exact?.topic_id;
  const details = topic ? await getTopic(topic, window, language) : null;
  return <div className="shell interior explore-page"><div className="eyebrow">FOLLOW YOUR CURIOSITY</div><h1>Explore conversations.</h1><p className="page-intro">One topic can open a much bigger picture.</p>
    <div className="explore-search"><SearchForm key={query} initialQuery={query} compact /><button type="button" className="quiet-action" disabled aria-disabled="true">Compare <span className="soon-label">Soon</span></button></div>
    {query && <div className="query-card"><span className="query-marker" /><div><span className="label">YOUR SEARCH</span><h2>{query}</h2></div><span className="pill">{details?.topic_type || (query.startsWith("#") ? "Hashtag" : "Keyword or phrase")}</span></div>}
    {!details && matches.length > 0 && <nav className="topic-matches" aria-label="Matching observed topics">{matches.map((item) => <Link className="suggestion-chip" key={item.topic_id} href={topicLink({ ...item, window_minutes: window, language })}>{item.label} · {item.topic_type}</Link>)}</nav>}
    <section className="explore-controls" aria-label="Explore filters"><label>Time range<select disabled defaultValue="summary"><option value="summary">{details ? `${windowLabel(window)} summary` : "Summary windows via Trending"}</option></select></label><label>Language<select disabled defaultValue={language}><option value="all">All languages</option><option value="en">English</option><option value="es">Spanish</option><option value="unknown">Unknown language</option><option value="other">Other languages</option></select></label><label>Source<select disabled defaultValue="bluesky"><option value="bluesky">Bluesky</option></select></label><span className="filter-note"><Info size={15} aria-hidden="true" /> Use Trending to change the summary window and language.</span></section>
    <section className="chart-panel" aria-labelledby="interest-title"><div className="chart-panel-heading"><div><span className="eyebrow">A CONVERSATION, OVER TIME</span><h2 id="interest-title">{details ? "Recent observed activity" : "Interest Over Time"}</h2></div><CollectionNotice state={state} /></div><div className="chart-canvas">{details ? <TopicSummary topic={details} /> : <DataEmptyState state={state} title={query ? `No analyzed history for “${query}” yet.` : "Your next question starts here."} description="Exact discovered topics have basic activity summaries. Full interactive comparisons are coming next." />}</div><div className="chart-footnote"><Info size={14} aria-hidden="true" /><span>Activity on Bluesky is not search interest. Coverage starts when collection begins.</span><Link href="/about#coverage">About coverage <ArrowRight size={13} aria-hidden="true" /></Link></div></section>
    <div className="explore-secondary"><section><span className="eyebrow">NEXT TO THE CONVERSATION</span><h2>Related topics</h2><p>Related discussions will be grounded in posts we actually observe.</p><div className="related-empty"><span className="related-mark">✳</span><span>No related topics yet</span></div></section><section id="comparison"><span className="eyebrow">SIDE BY SIDE, IN CONTEXT</span><h2>Compare conversations</h2><p>Compare up to five topics against the same measured time window.</p><Link className="text-link" href="/about#coverage">How comparisons will work <ArrowRight size={15} aria-hidden="true" /></Link></section></div>
  </div>;
}
