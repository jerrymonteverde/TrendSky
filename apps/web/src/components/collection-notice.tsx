import { Activity, CircleHelp, Database, Radio, Server } from "lucide-react";
import type { ReactNode } from "react";
import type { CollectionState, IngestionStatus } from "@/lib/api";

export function CollectionStatus({ data }: { data: IngestionStatus }) {
  const { status } = data;
  const unavailable = status === "unavailable";
  const collecting = status === "collecting" && (!data.health || data.health === "connected") && !data.cursor_expired && data.worker_fresh !== false;
  const persistenceFailure = data.health === "persistence_failure";
  const processing = data.health === "processing";
  const stopped = data.health === "stopped" && data.collection_started_at !== null;
  const interrupted = ["reconnecting", "interrupted", "error"].includes(status);
  const title = persistenceFailure ? "Collection needs attention" : processing ? "Processing Bluesky events" : stopped ? "Collection stopped" : collecting ? "Collecting Bluesky posts" : interrupted ? "Collection interrupted" : status === "connecting" ? "Connecting to Bluesky" : unavailable ? "Collection status unavailable" : "Collection not started";
  const description = data.cursor_expired ? "The replay window has expired. An operator needs to review recovery." : persistenceFailure ? "Database writes are failing. Progress is retained for safe recovery; operator review may be required." : processing ? "Connected to Bluesky. Waiting for a recent successful database write." : stopped ? "The collector has no fresh heartbeat. Previously stored observations remain available." : collecting ? "Observing public conversations in real time." : interrupted ? "Waiting to reconnect to Bluesky." : status === "connecting" ? "Establishing a connection to public Bluesky events." : unavailable ? "The data service can’t be reached right now." : "Live conversation data will appear once collection begins.";
  const updated = data.last_persisted_at ? new Date(data.last_persisted_at).toLocaleString() : "Not yet available";
  return <section className="collection-status" aria-label="Bluesky collection status">
    <div className="collection-primary"><span className="collection-icon"><Server size={19} strokeWidth={1.7} aria-hidden="true" /></span><div className="collection-copy"><span className="collection-label">DATA COLLECTION</span><p className="collection-title" role="status">{title}</p><p className="collection-description">{description}</p></div></div>
    <div className="collection-facts"><Fact icon={<Radio size={17} aria-hidden="true" />} label="SOURCE" value="Bluesky" /><span className="collection-separator" aria-hidden="true" /><Fact icon={<Activity size={17} aria-hidden="true" />} label="POSTS COLLECTED" value={unavailable ? "Not available" : data.posts_stored.toLocaleString()} /><span className="collection-separator" aria-hidden="true" /><Fact icon={<Activity size={17} aria-hidden="true" />} label="POSTS / MIN" value={collecting && data.posts_per_minute !== null ? data.posts_per_minute.toLocaleString() : "—"} /><span className="collection-separator" aria-hidden="true" /><Fact icon={<Activity size={17} aria-hidden="true" />} label="LAST UPDATE" value={updated} /></div>
    <span className={`collection-indicator ${collecting ? "is-live" : unavailable || interrupted ? "is-unavailable" : "is-idle"}`} aria-label={collecting ? "Collection active" : "Collection inactive"} />
  </section>;
}

function Fact({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="collection-fact"><span className="fact-icon fact-icon-muted">{icon}</span><div><span className="fact-label">{label}</span><span className="fact-value fact-muted">{value}</span></div></div>;
}

export function CollectionNotice({ state }: { state: CollectionState }) {
  const title = state === "not_started" ? "Collection not started" : state === "collecting" ? "Collecting Bluesky posts" : state === "connecting" ? "Connecting to Bluesky" : state === "unavailable" ? "Collection status unavailable" : "Collection interrupted";
  return <div className="collection-notice" role="status"><span className={`status-dot ${state === "unavailable" || state === "interrupted" || state === "reconnecting" || state === "error" ? "status-unavailable" : ""}`} aria-hidden="true" /><span>{title}</span><span className="notice-divider" aria-hidden="true" /><span className="source-label">Source: Bluesky</span></div>;
}

export function DataEmptyState({ state, title = "A clear view starts with real data.", description }: { state: CollectionState; title?: string; description?: string }) {
  const unavailable = state === "unavailable";
  const interrupted = ["interrupted", "reconnecting", "error"].includes(state);
  const connecting = state === "connecting";
  const emptyTitle = unavailable ? "Collection status is taking a moment." : interrupted ? "Collection has been interrupted." : connecting ? "Connecting to public conversations." : title;
  const emptyCopy = unavailable ? "The data service is temporarily unavailable. No activity values are shown." : interrupted ? "Some observation periods may be incomplete. Trend results will remain unavailable until there is enough verified coverage." : connecting ? "The collector is connecting. No activity values are shown until records arrive." : description || "Bluesky collection hasn’t started yet. Trending conversations will appear here once observations are available.";
  return <div className="data-empty"><div className="empty-symbol"><Database size={23} strokeWidth={1.7} aria-hidden="true" /></div>
    <p className="empty-kicker">{unavailable ? "A CONNECTION BREAK" : interrupted ? "COVERAGE NEEDS CARE" : "YOUR WINDOW INTO BLUESKY"}</p>
    <h3>{emptyTitle}</h3>
    <p className="empty-description">{emptyCopy}</p>
    <div className="empty-details"><span><CircleHelp size={14} aria-hidden="true" />{unavailable ? "Coverage cannot be verified" : interrupted ? "Missing periods are not zero activity" : "Coverage begins with collection"}</span></div>
  </div>;
}
