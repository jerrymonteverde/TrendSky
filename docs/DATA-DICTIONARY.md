# Data dictionary

All operational timestamps use timezone-aware UTC values. Migration `0001_sources` seeds one `data_sources` row; `0002_ingestion` adds the following entities.

## `posts`

| Column | Meaning |
| --- | --- |
| `uri` (PK) | Stable AT Protocol URI (`at://{did}/app.bsky.feed.post/{rkey}`); replay idempotence key |
| `did`, `rkey` | Public author identifier and record key |
| `text` | Latest observed public post text; nullable for invalid/missing record text. NUL characters are replaced with U+FFFD at persistence because PostgreSQL text cannot store U+0000 |
| `created_at` | Record creation timestamp, nullable unless valid and timezone-aware |
| `event_at` | Jetstream event timestamp |
| `ingested_at` | Local persistence time; retention basis |
| `event_seq` (unique) | Latest Jetstream sequence for this retained record |
| `languages` | Optional declared language values from record metadata |

Indexes: author DID and ingestion timestamp. Post updates replace the row; deletes remove it.

## `hashtags` and `post_hashtags`

`hashtags.id` is a surrogate key and `hashtags.tag` is unique normalized lowercase text. `post_hashtags` joins post URI to hashtag ID with cascading foreign keys and a composite primary key. Hashtags are extracted from text and explicit `app.bsky.richtext.facet#tag` features. Unreferenced tag rows are pruned during retention cleanup.

## `ingestion_state`

One row per source, seeded for `bluesky`. `status` is constrained to `not_started`, `connecting`, `collecting`, `reconnecting`, `interrupted`, or `error`. `last_seq` is the durable inclusive resume cursor. Lifecycle timestamps include collection start, current connection, latest event, latest persisted batch and heartbeat. `posts_per_minute` is a bounded rolling estimate and null when not actively collecting. `cursor_expired` marks operator intervention required. `last_error` is a short operational category/message and is not returned by public endpoints.

Cumulative counters: `total_events_received`, `valid_post_events`, `posts_persisted`, `duplicate_events`, `invalid_events`, `processing_errors`, and `reconnection_count`. They survive worker restart and retention cleanup; `posts_persisted` counts successfully written post records, not current unique rows.

## `collection_coverage`

Each row represents a successful socket session: `started_at`, optional `ended_at`, `start_seq`, most recently committed `end_seq`, `outcome`, and short `reason`. An open row can become stale after a process crash; heartbeat freshness must also be checked.

## `collection_gaps`

`gap_start_at`, `detected_at`, `resume_after_seq`, optional `resolution_seq` / `resolved_at`, `reason`, and `resolution_note` record known incomplete observation. A malformed event with a usable sequence can have a resolution boundary while remaining an unresolved analytical coverage warning. These records are not zero-activity observations.

## API contracts

- `GET /api/v1/ingestion/status`: effective state, current retained posts count, rate, event/persist/heartbeat timestamps, cursor, cursor-expiration flag.
- `GET /api/v1/ingestion/stats`: current retained count plus durable cumulative operational counters.
- `GET /api/v1/ingestion/coverage?limit=50`: newest coverage periods and known gaps; limit is bounded to 200.
- `GET /api/v1/analytics/summary`: backwards-compatible concise collection summary.

No credentials, media bytes, private messages, or arbitrary raw Jetstream frames are stored.

## Milestone 3 — revision `0003_trends`

| Table | Keys and values | Purpose |
| --- | --- | --- |
| `topics` | SHA-256 `id` PK; `kind`, `normalized`, `label`, `revision`; unique normalized/kind index | Stable distinct hashtag/keyword/phrase identities, display label, correction guard |
| `topic_jobs` | `post_uri` PK; `generation`, `touched_at`; timestamp/URI index | Transactional coalescing work queue, including tombstones; no text |
| `post_topics` | composite PK `(post_uri,topic_id)`; cascading foreign keys; `activity_at`, `language` | One mention per post/topic, exact contributor joins back to retained `posts` |
| `trend_snapshots` | composite PK `(topic_id,window_minutes,language)`; `topic_revision`, counts, scores, `as_of`, `calculated_at`, JSON `metrics` | Precomputed serving data and bounded historical windows |
| `trend_state` | source key `bluesky`; state/heartbeat/timestamps, processed posts, errors/backlog, durations, topic count, coverage warnings | Public safe worker observability |

`post_topics` indexes `(activity_at,language,topic_id)` and `(topic_id,activity_at)` support bounded range aggregation and topic lookup. Each ranking has a `(window_minutes,language,score,topic_id)` index. `posts_processed` counts successfully acknowledged URI jobs and can increase for later edits; it is not a unique post count. `topics_discovered` is the current retained topic registry size. Queue generations can advance several times before one processing pass.

Snapshot metrics include observed/current/previous post counts, distinct contributors, capped activity, growth/state, velocity, acceleration, robust median/MAD/deviation/lift, momentum, classification, coverage ratios, covered minutes and history. Previous activity is null unless its window is covered. Chart `posts` is null for incomplete windows while `observed_posts` can still report what was retained. Formula definitions and units are in [trend methodology](TREND-METHODOLOGY.md).

Source mutation triggers increment affected topic revisions, remove obsolete associations and labels, invalidate relevant saved snapshots, and enqueue the URI within the source transaction. A snapshot revision is a publication consistency guard, not a count or a Jetstream sequence. No source observation is removed by the upgrade migration.

## Milestone 3.1 operational semantics (no new columns)

`ingestion_state.last_error` may contain a parsed, maximum-160-character failure marker: mode (`blocked` or `retrying`), SQLSTATE or dash, error category, phase, 12-hex batch ID, batch size and safe sequence bounds. This contains no content/credentials. A blocked marker is a durable operator hold, not permission to advance the checkpoint. The existing coverage tables record its interruption. Arbitrary legacy error text is not exposed by the public API.

Derived ingestion response fields are `health`, `worker_fresh`, `persistence_fault`, `persistence_lag_seconds` and `event_lag_seconds`. Lag measures wall-clock age, not stream completeness. `connected` requires fresh heartbeat plus a recent successful commit; `processing` identifies a fresh socket waiting for that evidence. API rates are null for stale/unhealthy collection. Trend status independently reports health/freshness/backlog; stopped or stale analysis cannot publish current rankings. `/health.database_health` is available, degraded (SQL reachable but schema/readiness failed), or unavailable. None of these fields changes cumulative counter meanings or asserts complete Bluesky coverage.
