import { CircleHelp, Database, Radio } from "lucide-react";
import type { CollectionState } from "@/lib/api";

export function CollectionNotice({ state }: { state: CollectionState }) {
  return <div className="collection-notice" role="status"><span className="status-dot" /><span>{state === "not_started" ? "Collection not started" : "Collection status unavailable"}</span><span className="notice-divider" aria-hidden="true" /> <span className="source-label">Source: Bluesky</span></div>;
}
export function DataEmptyState({ state, title = "A clear view starts with real data.", description }: { state: CollectionState; title?: string; description?: string }) {
  return <div className="data-empty"><div className="empty-symbol"><Radio size={25} aria-hidden="true" /></div>
    <h3>{state === "unavailable" ? "We can’t check collection status right now." : title}</h3>
    <p>{state === "unavailable" ? "The data service is temporarily unavailable. Please try again later. No activity values are shown." : description || "Bluesky collection hasn’t started yet. Trending conversations will appear here once observations are available."}</p>
    <div className="empty-details"><span><Database size={14} aria-hidden="true" />{state === "not_started" ? "No observations collected" : "Data service unavailable"}</span><span><CircleHelp size={14} aria-hidden="true" />{state === "not_started" ? "Coverage begins with collection" : "Coverage cannot be verified"}</span></div>
  </div>;
}
