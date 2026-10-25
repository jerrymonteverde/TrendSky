import type { Metadata } from "next";
import { CollectionNotice, DataEmptyState } from "@/components/collection-notice";
import { getCollectionState } from "@/lib/api";
export const metadata: Metadata = { title: "Trending Now" };
export const dynamic = "force-dynamic";
export default async function Trending() {
  const state = await getCollectionState();
  return <div className="shell interior"><div className="eyebrow">WHAT’S GATHERING MOMENTUM</div><h1>Trending Now</h1><p className="page-intro">A window into rising public conversations on Bluesky.</p>
    <section className="trend-panel"><div className="panel-topline"><CollectionNotice state={state} /><span className="panel-caption">Ranking not available</span></div><DataEmptyState state={state} title="The next conversation is still ahead." description="Collection and trend ranking are not running yet. Topics will appear here when there is enough observed activity to measure momentum." /></section>
    <section className="explanation-section"><h2>Activity with perspective.</h2><p>Future rankings will consider velocity, acceleration and independent contributors alongside volume. Trend statuses and their mathematical definitions will be published with the ranking engine in Milestone 3.</p></section>
  </div>;
}
