# Milestone 2 — Real-time Bluesky ingestion

## Implemented

- Added an async worker package at `apps/api/trendsky_api/ingestion/`. It subscribes to Jetstream v2 post commits plus account/sync removal markers using the canonical XRPC path, required `xrpc.v1.json` subprotocol, and the `message.payload` event envelope.
- Uses a bounded queue (5,000 by default), bounded WebSocket receive queue, 250-event batches, 1-second flush target, capped database pool, exponential reconnect with jitter, safe SIGTERM/SIGINT shutdown, and periodic heartbeat/retention work.
- Persists public post text and required public record identifiers, optional declared languages and normalized hashtags. No media, private messages, credentials or raw frames are stored. Create/update upserts use AT URI; delete, deleted-account and sync-divergence markers remove current rows.
- Stores the inclusive Jetstream cursor in the same transaction as post changes and event counters. URI identity and sequence checks make replay idempotent. Failed transactions leave the cursor unchanged. Cursor-too-old conditions create a coverage gap and stop automatic restart for operator review.
- Added reversible Alembic revision `0002_ingestion`: `posts`, `hashtags`, `post_hashtags`, `ingestion_state`, `collection_coverage`, and `collection_gaps`.
- Added read-only `GET /api/v1/ingestion/status`, `/stats`, and `/coverage`; the existing summary now reports live status and current retained-row count. Stale heartbeats surface as interrupted.
- Connected the existing homepage/trending collection panel to actual status. It refreshes server data every 30 seconds while the page is visible, displays stored counts/rate/last persisted time, and explains cursor expiry. Existing visual design and empty trend states remain intact.
- Added dedicated Compose `ingestion` service, no published port, resource limits, graceful stop window, and successful migration dependency. Compose parsing passes.

## Protocol and data handling

The implementation uses the Jetstream v2 `/xrpc/network.bsky.jetstream.subscribeEvents` method and does not parse legacy v1 frames. V2 messages contain a typed `message` envelope and a typed payload. The v2 sequence cursor is an inclusive replay point; receiving a duplicate at that point is expected. See the official [Jetstream protocol and wire format](https://github.com/bluesky-social/jetstream/blob/main/docs/README.md) and [Bluesky Jetstream service docs](https://bsky.network/docs/jetstream/).

Only `app.bsky.feed.post` commits are requested; account/sync markers bypass collection filtering and are retained in the stream to honor deletions. Sequence numbers span source events, so sequence jumps alone are not proof of missing posts. Known disconnections, malformed events and cursor expiration are recorded as gaps, and analysis must not convert those periods into zero activity. See [data architecture](DATA-ARCHITECTURE.md) and [data dictionary](DATA-DICTIONARY.md).

Retention is 30 days by `ingested_at` by default. Cleanup runs hourly and deletes at most 5,000 rows per pass to limit transaction size. Cumulative event counters survive retention; `posts_stored` is the current retained count. The PostgreSQL operational store is not a full historical archive.

## Verification results

| Check | Result |
| --- | --- |
| Jetstream parser, URL, strict v2 framing and invalid-frame tests | Passed |
| SQLite store: insert, duplicate replay, update, delete, atomic rollback/checkpoint | Passed |
| SQLite worker session with deterministic fake WebSocket | Passed |
| SQLite Alembic migration upgrade/re-upgrade/schema parity/downgrade | Passed |
| Worker/store/API Python lint, formatting, mypy | Passed |
| Docker Compose configuration parse | Passed (`docker compose config --quiet`) |
| Frontend Vitest, ESLint, TypeScript and production build | Passed: 14 Vitest tests; lint, typecheck and Next.js webpack production build |
| PostgreSQL contract | Skipped; no disposable `TEST_DATABASE_URL` supplied |
| FastAPI API integration suite | Passed: 22 tests; PostgreSQL-only contract skipped without disposable `TEST_DATABASE_URL` |
| Responsive Playwright suite | Passed: 20 desktop/mobile Chromium tests |
| Compose startup / Docker image build / live Jetstream ingestion | Not verified; `/var/run/docker.sock` denies access and noninteractive sudo requires authentication |

No live post, event count, active connection, or successful PostgreSQL write is claimed. The worker uses thread-offloaded synchronous SQLAlchemy I/O as appropriate for production; deterministic worker tests inline that offload because this sandbox does not schedule its worker thread. The API suite and Playwright suite completed with the approved execution context.

## Run and monitor

Merge the settings below into `.env` without replacing existing secrets. Set `INGESTION_ENABLED=false` to keep the worker idle. Then, on a Docker-capable host:

```bash
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
docker compose ps
curl --fail http://localhost:8000/api/v1/ingestion/status
curl --fail http://localhost:8000/api/v1/ingestion/stats
curl --fail 'http://localhost:8000/api/v1/ingestion/coverage?limit=50'
docker compose logs --tail=100 ingestion
```

Stop collection without stopping the rest of TrendSky with `docker compose stop ingestion`. Restart with `docker compose start ingestion`. Inspect current retained rows and cursor using an administrative local database session:

```sql
SELECT count(*) AS posts_stored, max(event_at) AS latest_event_at FROM posts;
SELECT status, last_seq, heartbeat_at, posts_per_minute, cursor_expired FROM ingestion_state WHERE source_id = 'bluesky';
SELECT started_at, ended_at, start_seq, end_seq, outcome, reason FROM collection_coverage ORDER BY started_at DESC LIMIT 20;
SELECT detected_at, resume_after_seq, resolution_seq, resolved_at, reason FROM collection_gaps ORDER BY detected_at DESC LIMIT 20;
```

If Jetstream reports a cursor below its replay floor, do not silently clear it. Preserve the coverage gap, investigate supported replay/backfill for the affected period, or make an explicit operator-approved reset that records a new gap. Automatic historical backfill is outside this milestone. Troubleshoot endpoint/network availability, rate limits and service status before changing the configured host.

## Configuration defaults

`INGESTION_ENABLED=true`, `JETSTREAM_URL=wss://jetstream.us-east.bsky.network`, `INGESTION_BATCH_SIZE=250`, `INGESTION_FLUSH_INTERVAL_MS=1000`, `INGESTION_QUEUE_MAX_SIZE=5000`, `INGESTION_RETENTION_DAYS=30`, heartbeat every 15 seconds with 60-second freshness, reconnect base 1 second capped at 60 seconds. Worker Compose limit: 384 MiB and 1 CPU; pool size 2 plus at most 1 overflow connection.

## Known limitations

- This worker is not a historical archive and cannot guarantee complete network coverage. Replay has a limited horizon; no automatic backfill is present.
- Jetstream sync markers are destructive account-level reconciliation markers. Current posts are purged, but historical post text is not retained for audit/recovery.
- The API does not expose raw post text or admin controls. No trend ranking or aggregate topic analytics are implemented in this milestone.
- PostgreSQL-specific locking/upsert behavior and live Bluesky operation need verification on the host runtime. SQLite verifies persistence contracts; the PostgreSQL contract is skipped without a disposable test database.
- This sandbox can validate Compose syntax but cannot access the Docker daemon, so the containerized worker and live persistence could not be exercised.
