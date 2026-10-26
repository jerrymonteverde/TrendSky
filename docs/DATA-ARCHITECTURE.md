# Data architecture

## Milestone 2 operational flow

1. The worker requests Jetstream v2 commit, account and sync event kinds, with only the `app.bsky.feed.post` collection for commits.
2. V2 frames are parsed as the typed `message` envelope. Event kind, sequence, UTC timestamp and required public identifiers are validated. Malformed sequenced frames are recorded as coverage gaps; malformed frames without a safe cursor are also recorded and are never interpreted as zero activity.
3. A bounded in-memory queue limits buffering. At saturation, the async receiver waits and lets WebSocket flow control apply backpressure; it does not intentionally drop queue items.
4. The batch writer upserts by AT URI, replaces normalized hashtag relationships on updates, removes posts on delete/account deletion/sync divergence markers, then commits records, counters and the highest processed sequence atomically.
5. If the database transaction fails, it is retried a bounded number of times. The cursor is not advanced on rollback. A later replay is idempotent.
6. PostgreSQL serves operational status and collection coverage to FastAPI. The UI refreshes status periodically and only uses live values returned by the API.

## Coverage semantics

`collection_coverage` records successful socket periods, their sequence bounds, and closure outcome. A process crash may leave an open period; a stale heartbeat makes the public state `interrupted`, and the next worker start closes the previous period as `worker_restarted`. `collection_gaps` records known malformed events, Jetstream cursor errors, and unsequenced invalid frames. Sequence gaps in a filtered stream do not automatically mean lost events because Jetstream sequence numbers span events outside the selected collection.

The stored cursor is a resume position, not proof that every public post was observed. Replay is inclusive and at-least-once; URI and sequence checks protect persistence from replay duplication. Replay is limited. When too old, the worker does not reset to “now”: it records the gap and requires operator action. No automatic backfill is implemented. Analysis must treat known gaps and periods before first collection as unknown coverage, not zero activity.

## Retention and privacy

Only public post text, AT URI, author DID, record key, post/event/ingestion times, optional declared language values, and normalized hashtags are stored. No media, private messages, credentials, or inferred location are collected. Retention defaults to 30 days from ingestion; hourly cleanup deletes at most 5,000 expired records per pass and can continue on subsequent passes. Cumulative operational counters survive row expiry; `posts_stored` is the current retained row count. A source delete or synchronisation marker removes current stored records. Historic text is not retained as a tombstone.

## Scalability boundary

PostgreSQL is the low-latency operational store for this milestone. The worker pool is limited to three connections and the API pool is bounded. Heavy historical processing and derived Delta/Parquet datasets belong in later isolated jobs. Spark/Databricks do not run in the API or ingestion loop.

## Milestone 3 derived data

The operational post table remains authoritative. A transactional mutation trigger queues each changed URI once, incrementing its generation when it changes again before analysis. The queue deliberately has no post foreign key so deletion work survives the removed row. A generation check and source row locks prevent acknowledging a newer change with stale extraction output.

`post_topics` contains one association per post/topic, its analytical event time and one declared language group. It references retained posts and topics. Source updates remove old associations; source deletions and retention remove dependent data and orphan topic labels. Persisted numerical snapshots are invalidated when the source change affects their event-time horizon. Counts are corrected from retained observations at the next publication cycle.

The worker handles at most 500 posts per extraction transaction by default, with a small inter-batch pause and a 60-second publication target. Rolling 5/15/60/360/1440-minute windows end at a minute-aligned UTC boundary 60 seconds behind now. Up to six earlier complete windows support robust baselines. Queries read bounded event-time ranges and at most 500 candidate topics per window. A fixed snapshot contains exact distinct window contributors; per-bucket contributor counts are never summed to produce that number.

There is no materialized view refresh on HTTP requests. `trend_snapshots` is an ordinary indexed serving table. Saved history contains observed counts and null chart values where coverage is incomplete. Derived language groups are en/es/unknown/other, plus a separately aggregated all-language view. The first declared language is used; unknown metadata never defaults to English.

Coverage quality, source revision checks, queued historical corrections and stale timestamps gate publication/serving. See [trend methodology](TREND-METHODOLOGY.md) for formulas and missing-history rules. Public APIs return aggregate topics and counts, without author DIDs or raw post text.

### Source text compatibility discovered during Milestone 3 verification

A real checkpoint replay sample contained NUL characters in public post text, which PostgreSQL text cannot store. The ingestion persistence boundary replaces U+0000 with U+FFFD and logs the count after the batch commits. The post, timestamps and durable checkpoint remain in the same transaction; no cursor reset or source post deletion is used to bypass a bad record. The replacement retains the token boundary used by deterministic extraction. This normalization is disclosed because raw text is no longer byte-identical for those records.

### Milestone 3.1 correction and incident evidence

The preceding text-only normalization was incomplete: an explicit hashtag facet in the stalled cursor replay contained NUL. The same unsupported field pattern reproduced a `DataError` on actual PostgreSQL 18, rolling back the hashtag write and entire source transaction. Supported post text, hashtag values and language JSON strings are now normalized before binding; valid Unicode and emoji remain intact, while invalid scalars become replacement characters. Stable identifiers are validated rather than rewritten. Oversized normalized hashtags and other deterministic data failures hold for operator review instead of silently dropping the event or advancing the cursor.

No additional schema is required. The existing `ingestion_state.last_error` stores a bounded, parsed `blocked|...` marker containing only batch ID/size, sequence bounds, error category/SQLSTATE and processing phase. A coverage gap/period closure records the interruption. The next process start observes the hold. The failed source event remains available only through source replay/backfill, not a content quarantine; replay expiration is a documented recovery limitation. Marker acknowledgement must follow review and cannot reset the checkpoint or erase gaps.

Ingestion status now includes derived `health`, `worker_fresh`, safe `persistence_fault`, and event/persistence lag. A current socket/heartbeat without a recent durable write is processing, not connected collection; stale rates are hidden. Trend processor health and ranking freshness are independent. Cumulative metrics and current retained row count retain their earlier meanings.

[Recovery evidence](evidence/milestone-3.1-postgres.json) measures synthetic PostgreSQL persistence, queue drain and aggregation separately, including actual query plans and relation/index sizes. This supplements, without relabeling, the earlier SQLite benchmark. Production catalog/IO observations remain blocked. See the [recovery runbook](MILESTONE-3.1-RECOVERY-REPORT.md).
