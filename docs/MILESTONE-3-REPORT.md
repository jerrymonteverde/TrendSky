# Milestone 3 — Trending intelligence

## Subsequent recovery evidence — Milestone 3.1

The sections below retain the original Milestone 3 observations. For the current incident, use the [Milestone 3.1 recovery report](MILESTONE-3.1-RECOVERY-REPORT.md), which supersedes the historical rollout commands below. The earlier text-only NUL repair missed explicit hashtag metadata. The stalled-cursor facet defect has now been reproduced and repaired on actual isolated PostgreSQL 18, with safe diagnostics, operator holds, classified retries and separate operational health. No new operational migration is required at `0003_trends`.

Current verification: 84 backend tests passed with disposable PostgreSQL enabled; 22 frontend unit and 26 desktop/mobile browser tests passed; lint/type checks and production build passed. A 25,000-post PostgreSQL benchmark measured persistence and aggregation separately, with actual EXPLAIN/BUFFERS in [the evidence artifact](evidence/milestone-3.1-postgres.json). This supplements the earlier SQLite result without relabeling it.

Live recovery is still **Blocked** by Docker authorization. At 2026-10-26 04:55:05 UTC, the existing deployment remained at 167,331 posts and sequence `26446992220`. No collected data or checkpoint was changed. The existing backup is zero bytes; the recovery runbook requires a new validated backup and sustained write/restart/backlog verification before completion.

## Delivery state

**Implemented and tested offline; live PostgreSQL deployment remains Blocked.** The running ingestion API was observed collecting 23,720 retained posts at `2026-10-26T02:34:35Z`, about 2,011 posts/minute, with a valid checkpoint and no invalid-event/processing-error counts. Those values describe that observation, not a current guarantee. Docker daemon access is denied and `sudo -n docker compose ps` requires interactive authentication, so revision `0003_trends` and the new worker were not applied to the operational database here.

The illustrated interface, Ubuntu font, existing palette and source post columns are preserved. A late read-only check found the existing collector reconnecting with 86,856 retained posts and its last persistence at `2026-10-26T03:00:06Z`. Its API/database health remained ready. No new trend code had been deployed.

A current-tip Jetstream handshake succeeded with `xrpc.v1.json`. A bounded replay from the stuck checkpoint yielded 300 frames and 293 posts; six contained NUL characters that [PostgreSQL text columns cannot store](https://www.postgresql.org/docs/18/datatype-character.html). The existing worker reported 30 processing errors. A narrow persistence compatibility fix replaces source NUL characters with U+FFFD, preserves the post and atomic checkpoint, and logs the number of normalized records after a successful commit. This avoids dropping the entire batch or resetting progress. A deterministic regression test verifies storage and checkpoint advancement. Deployment is still required to confirm the live collector recovers.

The same in-memory real-source sample produced 1,012 topic associations with 139 English, one Spanish, 100 unknown-language and 53 other-language posts. Only aggregate diagnostic counts were retained; no post text, author IDs or real dataset was committed. These diagnostics are not published trend statistics. See [live probe evidence](evidence/milestone-3-live-probe.json).

No Spark, Databricks, ML model, LLM explanation, source-data reset, volume cleanup, Caddy deployment or unrelated Docker operation was performed.

## Implemented behavior

- Deterministic hashtags, English/Spanish keywords and reviewed phrase lexicon. Unicode NFKC/casefold normalization, stopwords, URL/spam filtering, duplicate-mention exclusion and stable typed IDs.
- Transactional URI change queue that handles existing observations, new posts, edits, deletes, account/sync purges and retention. Queue acknowledgement and per-post replacement are atomic; restart does not inflate associations.
- Event-time rolling windows: 5/15/60/360/1440 minutes, minute-aligned UTC ends, a default 60-second lateness buffer and comparable previous windows.
- Actual observed counts, distinct contributors, contributor-capped activity, velocity, growth, acceleration, robust median/MAD/deviation/lift and bounded momentum.
- Separate Popular Now, Rising Fast and Emerging ranks. Deterministic Emerging/Rising/Stable/Declining/Insufficient Data classifications and explicit coverage/freshness fields.
- Background SQL aggregation and indexed saved snapshots. HTTP requests perform serving queries, not analytical recomputation.
- Homepage measured cards, exact artwork mapping and neutral fallback; ranking tabs, time/language controls, pagination, basic Explore summaries and recent-window history.
- Safe worker status with heartbeat, backlog, cumulative acknowledged jobs, topic count, errors and measured durations.

## Database and correction design

Primary changed files and areas:

| Area | Files |
| --- | --- |
| Statistical engine | `apps/api/trendsky_api/trends/`: extraction, coverage, statistics, models, processor, worker, API and schemas |
| Schema and configuration | `apps/api/migrations/versions/0003_trends.py`, migration metadata registration, `config.py`, API readiness/router registration |
| Observed ingestion compatibility | `apps/api/trendsky_api/ingestion/store.py`, NUL regression test |
| Frontend | `lib/trends.ts`, trend card/results and topic-summary components, homepage, Trending and basic Explore integration; About copy now reflects measured analytics |
| Infrastructure | `docker-compose.yml`, `.env.example`, CI synthetic API/disabled live ingestion, runtime smoke contract |
| Validation | Extraction/statistics/SQL/API/PostgreSQL tests, isolated browser fixture, `scripts/validate_trends.py` and evidence artifacts |
| Documentation | README, architecture, data architecture/dictionary, methodology, implementation status and this report |

Revision `0003_trends` adds `topics`, `topic_jobs`, `post_topics`, `trend_snapshots` and `trend_state`. It creates range/lookup/ranking indexes, installs source mutation triggers, then seeds existing post URIs once. PostgreSQL DDL lock acquisition is bounded to two seconds and statements to thirty seconds during the migration. Capture is installed before seeding, preventing a source-write race. The upgrade preserves source observations; test downgrades run only against isolated fixture databases.

The trigger invalidates snapshots whose horizons contain an edited/deleted association, removes obsolete associations and orphan labels, increments source topic revisions and queues the URI in the source transaction. The processor acknowledges only the generation it inspected. A sequence alone cannot detect deletion/retention changes, which motivated this queue design.

The background processor uses bounded batches, `SKIP LOCKED`, a transaction advisory lock, a 100 ms analytical lock timeout and a 10-second statement timeout. Snapshot publication captures topic revisions before aggregate reads and rechecks them under short topic locks. Normal posts after a saved boundary do not erase that valid earlier result. Source corrections and late events before the boundary invalidate affected saved results until recalculation.

PostgreSQL aggregation uses [GROUPING SETS](https://www.postgresql.org/docs/18/queries-table-expressions.html) for per-language/all-language contributor groups, then caps each author's window contribution at three posts. SQLite uses a tested union equivalent. The source-capture mechanism follows PostgreSQL's [row trigger transaction behavior](https://www.postgresql.org/docs/18/sql-createtrigger.html). No materialized-view refresh is invoked in requests.

## Statistical methodology

The full, versioned definitions are in [TREND-METHODOLOGY.md](TREND-METHODOLOGY.md). In brief, growth is `100*(C-P)/P` only for two covered windows and a nonzero previous count. A zero previous count yields explicit new activity with null percentage. Velocity divides by observed minutes. Acceleration is `(C-P)/w²`, in posts/minute². Three or more complete earlier windows are required for baseline statistics; zero MAD yields null deviation.

Default normal minima are 5 posts and 3 contributors; emerging minima are 10 posts and 5 contributors. Growth/decline thresholds are ±25%, and unusual baseline lift is 2. Momentum combines bounded capped volume, participation, capped growth and baseline elevation with weights 0.25/0.25/0.35/0.15. Popularity uses `ln(1+capped_posts)*ln(1+contributors)`. Rising and Emerging have distinct eligibility rules and scores. Scores are descriptive; no significance test or prediction is claimed.

Known gaps, disconnected periods, pre-collection history and retention boundaries prevent unavailable intervals becoming zeros. Complete observed windows describe collector coverage and do not imply full network representation. Publication waits for queued changes affecting its historical boundary. Topic counts overlap across topics, and language grouping uses declared metadata without inferring English for missing tags.

## API and frontend contracts

| Endpoint | Behavior |
| --- | --- |
| `/api/v1/trending` | Category/window/language/min-activity filters, bounded limit/offset, saved result page |
| `/api/v1/trending/popular`, `/rising`, `/emerging` | Same contract with explicit ranking category |
| `/api/v1/trending/status` | Safe operational status, freshness, backlog, durations and candidate cap |
| `/api/v1/topics/search` | Escaped normalized prefix query over retained topic registry |
| `/api/v1/topics/{id}` and `/{id}/activity` | Basic metadata, saved metrics and bounded recent history; no raw posts or author identities |

The homepage asks for three Popular Now topics in a 5-minute window. Trending has shareable category/window/language parameters and 12 results per page. Existing server refresh runs every 30 seconds while visible. Basic Explore resolves exact topic labels or stable card IDs; full comparisons remain Milestone 4. Sparklines appear only when every supplied historical point has covered data. Existing WebP art is selected by explicit exact aliases; unmatched topics render clean cards without guessed artwork.

## Validation and measurements

The synthetic scenarios are independently specified in `tests/api/trend_fixtures.py`, never loaded by the application. `scripts/validate_trends.py` seeds an isolated temporary SQLite database, runs migrations and the real processor, validates expected results and records query plans. Browser CI uses a separate synthetic HTTP fixture in `tests/e2e/`; no normal test requires Bluesky.

| Synthetic scenario | Current / previous | Expected and observed result |
| --- | --- | --- |
| Consistently popular | 12 / 12; 10 current contributors | 0% growth, Stable |
| Rapidly growing | 20 / 8; 10 current contributors | 150% growth, Rising |
| Declining | 4 / 12 | -66.6667% growth, Declining |
| Newly active | 10 / 0; 10 contributors | null growth, New activity, Emerging |
| Single contributor | 50 / 4 | Excluded from rankings |
| Missing current interval | 20 / 8 observed | null growth/acceleration; partial coverage and null chart point |
| Three deleted current posts | 8 becomes 5; previous 8 | -37.5% after invalidation/recalculation |

Actual evidence: [milestone-3-synthetic.json](evidence/milestone-3-synthetic.json). The final 25,000-post synthetic run extracted all 25,000 URI jobs in **9,345.301 ms**, with **96,120 KiB** Linux peak process RSS. Python 3.14.4; Linux x86_64; 12 logical CPUs; shared host with no dedicated CPU reservation. The filler intentionally repeats a small vocabulary; this measures bounded row processing rather than the lexical diversity of real Bluesky traffic. A separate test checks candidate caps and deterministic ties. These are single-run SQLite measurements and do not predict production throughput or measure trigger overhead on PostgreSQL.

| Window | SQL aggregate time | Complete refresh time |
| --- | ---: | ---: |
| 5 minutes | 228.84 ms | 252.70 ms |
| 15 minutes | 561.82 ms | 605.28 ms |
| 1 hour | 721.63 ms | 844.11 ms |
| 6 hours | 719.71 ms | 840.91 ms |
| 24 hours | 719.66 ms | 840.95 ms |

SQLite's query plan uses both event-range/topic indexes and temporary B-trees for distinct/group/order work. PostgreSQL `EXPLAIN ANALYZE`, live ranking latency and source ingestion impact could not be measured here. An optional isolated-schema PostgreSQL contract exercises actual grouping sets, triggers, replay safety and `EXPLAIN (ANALYZE, BUFFERS)` when `TEST_DATABASE_URL` is supplied.

Verification: Python tests **49 passed, 2 skipped** (the two PostgreSQL-specific contracts); frontend **19 unit tests passed**; **26 Playwright desktop/mobile checks passed**; Ruff check/format, mypy, frontend lint, type checking, production build and Compose syntax validation passed. Browser tests cover measured cards, existing artwork, themes, search, ranking navigation, filters, empty/error responses, topic history and horizontal overflow. Runtime Docker/operational PostgreSQL verification is explicitly outstanding.

## Operations

Defaults: batches 500; extraction loop pauses 0.25 seconds with backlog or 1 second while idle; snapshot refresh target 60 seconds; candidate cap 500 per window; baseline six windows with at least three complete; snapshot expiry 180 seconds. Compose gives `trends` 384 MiB, 0.5 CPU, two database connections, no published port, a 30-second shutdown grace and successful migration dependency. Transient database failures retry with a capped delay and structured error categories.

For an existing collecting installation, merge `.env.example` without replacing secrets, then run sequentially:

```bash
docker compose build migrate api ingestion trends web
docker compose run --rm --no-deps migrate
docker compose up -d --no-deps api ingestion trends web
docker compose logs --tail=100 trends
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8000/api/v1/trending/status
curl --fail 'http://localhost:8000/api/v1/trending/popular?window=5&language=all'
curl --fail 'http://localhost:8000/api/v1/trending/rising?window=5'
curl --fail http://localhost:8000/api/v1/ingestion/status
```

If the migration fails, stop the sequence and inspect its logs before starting the new API. These commands preserve the source database and volume, recreate the ingestion process with the text compatibility fix, and do not activate the optional Caddy profile. The collector resumes its committed inclusive cursor. To stop only analysis: `docker compose stop trends`. To disable on next creation: set `TRENDS_ENABLED=false`. Backlogged source changes remain durable for later processing.

Useful read-only database checks:

```sql
SELECT status, heartbeat_at, last_calculated_at, backlog, posts_processed FROM trend_state;
SELECT count(*) FROM topic_jobs;
SELECT kind, count(*) FROM topics GROUP BY kind;
SELECT window_minutes, language, count(*) FROM trend_snapshots GROUP BY 1,2 ORDER BY 1,2;
```

## Limitations and next steps

- Operational PostgreSQL migration, trigger overhead, query plans, new worker deployment and live frontend rankings require host Docker permissions. This is the remaining acceptance gate.
- The candidate cap and extraction caps bound resource use and can omit lower-frequency topics. This is an explainable baseline, with limited spam resistance and no bot/coordination detector.
- English/Spanish stopwords and a phrase allowlist are conservative. Declared language can be wrong; semantic topic merging and broad multilingual NLP are not implemented.
- History is based on retained current records, with deletion/retention correction; it is not a permanent archive. Sparse or broken coverage yields unavailable comparisons.
- Related-topic co-occurrence, full interactive Explore/Compare, exports and a shared relative-interest index remain subsequent work. No predictive model is included.
- After live acceptance, review topic quality on a small real sample and measure PostgreSQL plans/CPU/ingestion impact before raising caps or changing ranking weights. Preserve this version as an interpretable baseline for later offline ranking experiments.
