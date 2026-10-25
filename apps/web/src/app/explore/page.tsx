import type { Metadata } from "next";
import { Info } from "lucide-react";
import { SearchForm } from "@/components/search-form";
import { CollectionNotice, DataEmptyState } from "@/components/collection-notice";
import { getCollectionState } from "@/lib/api";
import { normalizeQuery } from "@/lib/search";
export const metadata: Metadata = { title: "Explore" };
export const dynamic = "force-dynamic";
export default async function Explore({ searchParams }: { searchParams: Promise<{ q?: string | string[] }> }) {
  const params = await searchParams;
  const query = normalizeQuery(typeof params.q === "string" ? params.q : "");
  const state = await getCollectionState();
  return <div className="shell interior"><div className="eyebrow">FOLLOW YOUR CURIOSITY</div><h1>Explore conversations.</h1><p className="page-intro">A little context can change how you see a conversation.</p>
    <SearchForm key={query} initialQuery={query} compact />
    {query && <div className="query-card"><span className="query-marker" /><div><span className="label">Your search</span><h2>{query}</h2></div><span className="pill">Keyword / phrase</span></div>}
    <div className="filter-row"><label>Time range<select disabled defaultValue="none"><option value="none">No collected history</option></select></label><label>Language<select disabled defaultValue="all"><option value="all">All languages</option></select></label><label>Data source<select disabled defaultValue="bluesky"><option value="bluesky">Bluesky</option></select></label></div>
    <div className="inline-note"><Info size={16} aria-hidden="true" /><p>Filters and analytics become available after collection begins. This search is saved in the URL; matching is not running yet. Semantic search is not implemented.</p></div>
    <section className="trend-panel"><div className="panel-topline"><h2>Interest Over Time</h2><CollectionNotice state={state} /></div><DataEmptyState state={state} title={query ? `No collected history for “${query}” yet.` : "Your next question starts here."} description="No historical data has been collected. Charts, summary metrics and exports will be available once observations exist." /></section>
    <section id="comparison" className="explanation-section"><h2>Context through comparison.</h2><p>Topic comparison is planned for Milestone 4. Up to five topics will share a time axis and a common relative-interest reference. Counts will describe observed posts, and overlapping matches will be explained.</p></section>
  </div>;
}
