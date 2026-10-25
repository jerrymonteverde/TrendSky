import Link from "next/link";
import { ArrowRight, ChartNoAxesCombined, GitCompareArrows, Search, Telescope } from "lucide-react";
import { SearchForm } from "@/components/search-form";
import { CollectionNotice, DataEmptyState } from "@/components/collection-notice";
import { getCollectionState } from "@/lib/api";

export const dynamic = "force-dynamic";
const features = [
  { number: "01", icon: Search, title: "Explore Conversations", copy: "Follow a question. Find the conversation around it.", href: "/explore", label: "Start exploring" },
  { number: "02", icon: GitCompareArrows, title: "Compare Topics", copy: "Put conversations side by side for a wider perspective.", href: "/explore#comparison", label: "About comparisons" },
  { number: "03", icon: ChartNoAxesCombined, title: "Discover Emerging Trends", copy: "Understand which conversations are gathering momentum.", href: "/trending", label: "Explore trending" },
  { number: "04", icon: Telescope, title: "Predict Future Activity", copy: "Look ahead with measured models and clear limitations.", href: "/predictions", label: "About predictions" },
];
export default async function Home() {
  const state = await getCollectionState();
  return <>
    <section className="hero shell" aria-labelledby="hero-title"><div className="eyebrow"><span className="tiny-sky" /> A NEW PERSPECTIVE ON CONVERSATION</div>
      <h1 id="hero-title">Discover what’s <span>rising.</span></h1>
      <p className="hero-subtitle">Explore conversations, compare trends, and discover what might happen next.</p>
      <SearchForm />
      <div className="hero-footnote"><span className="bluesky-mark" aria-hidden="true">✦</span><span>Big conversations. Clearer signals. Powered by Bluesky.</span></div>
    </section>
    <section className="trending-section shell" aria-labelledby="trending-title"><div className="section-heading"><div><div className="eyebrow">THE CONVERSATION, IN FOCUS</div><h2 id="trending-title">Trending Right Now</h2></div><Link className="text-link" href="/trending">View all trends <ArrowRight size={16} aria-hidden="true" /></Link></div>
      <div className="trend-panel"><div className="panel-topline"><CollectionNotice state={state} /><span className="panel-caption">Observed conversation activity</span></div><DataEmptyState state={state} /><div className="panel-footer"><span>Real observations. Transparent coverage.</span><Link href="/about#coverage">How we measure <ArrowRight size={14} aria-hidden="true" /></Link></div></div>
    </section>
    <section className="possibilities shell" aria-labelledby="possibilities-title"><div className="section-heading"><div><div className="eyebrow">FROM CURIOSITY TO CONTEXT</div><h2 id="possibilities-title">There’s more to every conversation.</h2></div><span className="section-aside">A foundation for what comes next.</span></div>
      <div className="feature-grid">{features.map(({ number, icon: Icon, title, copy, href, label }) => <article key={number} className="feature"><div className="feature-top"><Icon size={23} strokeWidth={1.5} aria-hidden="true" /><span>{number}</span></div><h3>{title}</h3><p>{copy}</p><Link href={href}>{label}<ArrowRight size={15} aria-hidden="true" /></Link></article>)}</div>
    </section>
    <section className="transparency-band"><div className="shell transparency-inner"><div className="transparency-symbol" aria-hidden="true">↗</div><div><h2>More context. Less guesswork.</h2><p>TrendSky measures observed public conversations on Bluesky. Every insight starts with knowing what the data can—and can’t—tell us.</p></div><Link className="text-link" href="/about">Our approach <ArrowRight size={16} aria-hidden="true" /></Link></div></section>
  </>;
}
