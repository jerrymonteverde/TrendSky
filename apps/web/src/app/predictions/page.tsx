import type { Metadata } from "next";
import { Telescope } from "lucide-react";
import Link from "next/link";
export const metadata: Metadata = { title: "Predictions" };
export default function Predictions() {
  return <div className="shell interior"><div className="eyebrow">A THOUGHTFUL LOOK AHEAD</div><h1>What might happen next?</h1><p className="page-intro">Future activity, with evidence behind every estimate.</p>
    <section className="trend-panel prediction-empty"><div className="empty-symbol"><Telescope size={28} aria-hidden="true" /></div><span className="pill">Models not available</span><h2>Good predictions take a little history.</h2><p>No models have been trained or evaluated. Forecasts will appear only after sufficient history, chronological validation and baseline comparison.</p><Link href="/about#predictions" className="text-link">Our approach to uncertainty <span aria-hidden="true">↗</span></Link></section>
    <div className="principles-grid"><article><span className="label">01 / OBSERVE</span><h2>Start with real activity.</h2><p>Collected observations and coverage come before modelling.</p></article><article><span className="label">02 / EVALUATE</span><h2>Earn the forecast.</h2><p>Compare models against simple baselines on future, unseen periods.</p></article><article><span className="label">03 / EXPLAIN</span><h2>Show the limitations.</h2><p>Publish model versions, measured errors and validated uncertainty.</p></article></div>
  </div>;
}
