import type { Metadata } from "next";
import { ArrowRight, Clock3, Telescope } from "lucide-react";
import Link from "next/link";
export const metadata: Metadata = { title: "Predictions" };
export default function Predictions() {
  return <div className="shell interior predictions-page"><div className="eyebrow">A THOUGHTFUL LOOK AHEAD</div><h1>What might happen next?</h1><p className="page-intro">Future activity, with evidence behind every estimate.</p>
    <div className="forecast-horizon"><span><Clock3 size={17} aria-hidden="true" /> FORECAST HORIZON</span>{["1 hour", "6 hours", "24 hours"].map((horizon) => <button type="button" key={horizon} disabled aria-label={`${horizon} forecast horizon, unavailable`}>{horizon}</button>)}</div>
    <section className="forecast-panel"><div className="forecast-context"><span className="eyebrow">AN HONEST LOOK AHEAD</span><div className="forecast-illustration" aria-hidden="true"><span className="horizon-line"/><span className="horizon-node node-one"/><span className="horizon-node node-two"/><span className="horizon-node node-three"/><Telescope size={25} strokeWidth={1.4}/></div><span className="pill pill-neutral">Models not available</span></div><div className="forecast-message"><h2>Good predictions take a little history.</h2><p>No models have been trained or evaluated. Forecasts will appear after collection starts, enough history is available, and models have been tested against future unseen periods.</p><Link className="text-link" href="/about#predictions">How we evaluate forecasts <ArrowRight size={15} aria-hidden="true" /></Link></div></section>
    <div className="principles-grid"><article><span className="label">01 / OBSERVE</span><h2>Start with real activity.</h2><p>Collected observations and coverage come before modelling.</p></article><article><span className="label">02 / EVALUATE</span><h2>Earn the forecast.</h2><p>Compare models against simple baselines on future, unseen periods.</p></article><article><span className="label">03 / EXPLAIN</span><h2>Show the limitations.</h2><p>Publish model versions, measured errors and validated uncertainty.</p></article></div>
  </div>;
}
