# Milestone 3.1 — ingestion incident recovery

Status: **In Progress; operational deployment and sustained recovery Blocked**. Reviewed 2026-10-25 America/Hermosillo (2026-10-26 UTC). No operational records, checkpoints, schemas, volumes or containers were changed in this execution. No unrelated Docker project was accessed.

## Incident and confirmed cause

The reachable API reported 167,331 retained posts, cursor `26446992220`, reconnecting ingestion, and a stale trend processor. Persistence was stalled despite continued heartbeats. The existing formatter hid `extra` diagnostics, and deterministic SQLAlchemy failures received the same retries as transient failures, followed by reconnect/replay.

A read-only Jetstream replay of 500 frames from the stalled cursor found a post at sequence `26446992388` with NUL in both its text and explicit hashtag facet. The earlier repair covered only `posts.text`. The facet reached `hashtags.tag` unchanged. A synthetic equivalent reproduced a PostgreSQL 18 `DataError`; this adapter-side failure had no SQLSTATE. Posts, trigger-generated jobs and the checkpoint all rolled back. This confirms the field-level defect and explains why stopping the trends process did not remove it. Direct deployed SQL logs/catalog inspection remains unavailable, so additional operational faults are not ruled out.

The persistence transaction also invokes the `0003_trends` mutation trigger: topic revision/snapshot invalidation, obsolete association cleanup, orphan-topic cleanup and coalesced durable job insertion happen even when the trends container is stopped. No evidence justified changing that trigger or a business formula. See [incident analysis](INGESTION-INCIDENT-ANALYSIS.md) for the complete write trace and evidence boundaries.

## Implemented corrections

- Normalize U+0000 to U+FFFD in post text, language JSON strings and hashtags at the persistence boundary. Preserve valid Unicode, multilingual text and emoji; replace malformed surrogate scalars while preserving valid surrogate pairs. Only supported stored fields are normalized; raw facets/media are not stored.
- Validate stable identifiers and database limits without rewriting identities or silently truncating values. Unsupported records require review.
- Keep posts, hashtag relations, trigger jobs, counters and checkpoint atomic. Inclusive replay remains idempotent. No failed record is skipped to advance progress.
- Emit allowlisted JSON worker logs: exception class, static safe message, SQLSTATE when supplied, structural constraint identifiers, phase, batch correlation ID/size/sequence range, attempt and delay. Stack locations omit source lines, values and chained exception rendering. SQL parameters, driver messages, DIDs, post text and connection strings are excluded. Engines hide parameters as additional protection.
- Retry connection, lock/statement timeout, deadlock, serialization and resource failures with bounded per-batch exponential backoff/jitter, then reconnect from the durable cursor. Data, integrity, schema and unexpected deterministic failures hold for review immediately.
- Persist a bounded `blocked|...` diagnostic marker in existing `ingestion_state.last_error`, record a coverage limitation, and stop automatic replay. Restart respects the hold. This is an **operator-intervention policy**, not an event quarantine/archive: event content is not copied, and the checkpoint stays before the failed batch. Replay availability is finite; historical recovery may be required after delay. Failure to persist the marker is itself logged safely; the running process still holds, but a subsequent restart cannot rely on a marker that never committed.
- Expose additive ingestion health/freshness/fault/lag fields. A socket without a recent successful commit is `processing`, not healthy collection. Stale heartbeats suppress rates. A persistence failure does not masquerade as ordinary reconnecting.
- Expose separate trend health (`running`, `processing_backlog`, `up_to_date`, `delayed`, `error`, `stopped`). Stopped/stale/error processors cannot publish rankings as current. Graceful shutdown records stopped state.
- `/health` retains existing fields and adds `database_health`: available after database/schema probes, degraded when SQL connectivity succeeds but schema/readiness fails, unavailable when connectivity cannot be established. This is not a general disk/latency diagnosis.
- Make catch-up pause configurable with `TRENDS_BATCH_PAUSE_SECONDS=0.25` (minimum 0.1). Existing 500-job batches, small pools, transaction timeouts, candidate limits and Compose resource limits remain.
- Preserve existing hero, assets, typography, palette and layout. Only operational copy and live-indicator conditions changed. Ingestion and ranking interruptions are described separately.

## Files created or changed in this recovery

| Area | Files |
| --- | --- |
| Safe diagnostics | `apps/api/trendsky_api/observability.py`, `operations.py` |
| Ingestion repair | `ingestion/text.py`, `failures.py`, `store.py`, `worker.py`, `protocol.py` |
| API and health | `database.py`, `config.py`, `main.py`, `schemas.py`, `trends/api.py`, `trends/schemas.py`, `trends/worker.py` |
| Operational UI only | `apps/web/src/lib/api.ts`, `components/collection-notice.tsx`, `components/trending-results.tsx` and their component tests |
| Regression tests | `tests/api/test_recovery.py`, `test_recovery_postgres.py`, `test_safe_logging.py`, `test_ingestion_protocol.py`, `test_api.py`, `test_trend_api.py` |
| Operational validation | `scripts/benchmark_recovery_postgres.py`, `scripts/verify_recovery.py`, two `docs/evidence/milestone-3.1-*.json` artifacts |
| Configuration | `.env.example`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.gitignore` |
| Documentation | README, architecture/data architecture/dictionary, implementation status, Milestone 3 report, incident analysis and this report |

The working tree already contained substantial uncommitted work before this incident task. No unrelated work was reset, committed or pushed. No migration, ranking/statistics formula, media asset or styling file was changed by this recovery.

## Database changes and data protection

**No new migration or operational DDL is required.** Existing revision `0003_trends` was tested on disposable PostgreSQL, including triggers and correction behavior. Production revision must still be inspected before deployment. The existing operational state/coverage tables store failure metadata. Never downgrade/reseed production as a recovery step.

The project filesystem had approximately 304 GiB free at audit. `backups/trendsky-before-milestone3.dump` was **zero bytes** and is not a backup. `backups/` is now ignored by Git (already excluded from Docker context). No backup was created or validated against production because Docker access was denied. Directory/archive inventory checks alone are not a tested restore.

## Verification and measurements

Actual PostgreSQL **18.0** was built from checksum-verified official source in a private temporary directory. Tests used a private Unix socket, no TCP listener, an explicitly disposable database and unique synthetic test schemas. Settings included 32 MiB shared buffers, 20 connections and fsync enabled. Test schema cleanup affected only that isolated instance. The instance uses tmpfs; it cannot establish host/VPS disk behavior or production checkpoint pressure.

Backend suite: **84 passed** including actual PostgreSQL migrations, JSON/text/facet compatibility, trigger insert/update/delete, replay idempotency, checkpoint/queue rollback, an actual constraint violation, actual lock timeout followed by retry, terminated pooled connection recovery, safe diagnostics, worker hold across restart, coverage, extraction, statistics, retention correction and APIs. No routine test depends on live Bluesky. Final quality/test output is recorded in the implementation tracker; browser checks use a synthetic test-only HTTP API, never product data.

| Executed check | Result |
| --- | --- |
| `pytest tests/api -q --tb=short` with disposable PostgreSQL URL | 84 passed, final run 4.89 seconds |
| `npm test` | 22 passed |
| `npm run test:e2e` with installed Chromium | 26 passed, desktop/mobile projects; about 1.5 minutes |
| `npm run lint`, `npm run typecheck`, `npm run build` | Passed |
| Ruff lint/format, strict mypy, `git diff --check` | Passed |
| `docker compose config --quiet` | Passed, daemon access not required |
| Operational Docker build/start, sustained repaired live observation/restart | Not executed; blocked by permissions |

The private PostgreSQL test server was stopped cleanly after validation. No test instance remains running alongside the operational services.

The [PostgreSQL benchmark artifact](evidence/milestone-3.1-postgres.json) contains actual `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, relation/index sizes and bounded catalog diagnostics:

| Measurement | Observed value |
| --- | ---: |
| Synthetic source posts persisted | 25,000 |
| Batch size / batches | 250 / 100 |
| Median / p95 / max persistence latency | 148.97 / 416.90 / 449.88 ms |
| Persistence throughput, summed write time | 1,294.93 posts/s |
| Queue backlog processed | 25,436 (includes 436 scenario posts) |
| Extraction/queue drain | 30.74 s |
| All five window refreshes | 3.51 s |
| Individual window SQL time | 205.92–583.40 ms |
| Synthetic rocket scenario | 20 current posts, 150% growth |

The benchmark uses 50 repeating synthetic hashtag topics, a limited vocabulary and 300 authors, without Compose CPU caps or inter-batch pacing. Production has much greater topic diversity. These are measurements of this fixture, not a capacity guarantee, improvement claim or evidence that WAL/disk caused the incident. Cluster WAL/checkpoint counters are cumulative, not a benchmark-exclusive delta. Detailed host I/O, production table/index sizes, blocking activity and sustained ingestion impact remain unmeasured.

## Safe deployment procedure — operator required

Run from this repository, using `sudo docker` if interactive Docker authorization is required. These commands target only TrendSky. Do not enable the Caddy profile, stop unrelated containers, reset cursors or use volume cleanup.

1. Inspect `docker compose ps` and `df -h .`. Record current `/ingestion/status`, `/ingestion/stats`, `/trending/status` and `/health`. Inspect `docker compose logs --tail=100 ingestion trends` locally. Old logs may lack detail; avoid sharing unredacted SQL/credentials.
2. Create a new consistent backup with private permissions. Preserve the old file; do not overwrite it:

```bash
set -euo pipefail
umask 077
mkdir -p backups
backup_path="backups/trendsky-recovery-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db sh -c 'pg_dump -U postgres -d "$POSTGRES_DB" -Fc' > "$backup_path"
test -s "$backup_path"
docker compose exec -T db pg_restore --list < "$backup_path" > /dev/null
```

Stop if dump/inventory validation fails. Confirm a restore in a separate disposable database before any future destructive migration/restore. No destructive operation is part of this repair.

3. Build changed application images and inspect the deployed database using the read-only diagnostics module (5-second statement / 100-ms lock deadlines per query, no row content or SQL text from active sessions):

```bash
docker compose build api ingestion trends web
docker compose run --rm --no-deps api python -m trendsky_api.operations
docker compose run --rm --no-deps api alembic current
```

Require revision `0003_trends` and available expected relations. If the deployed revision differs, stop and review the incremental migrations, backup/restore evidence and lock impact with the operator. Do not blindly rerun/downgrade migrations. No migration is needed when already at `0003_trends`.

4. Keep a currently stopped trend processor stopped while verifying ingestion. If running, an operator can stop **only** `trends` for isolation. Recreate just the changed API, web and ingestion processes:

```bash
docker compose up -d --no-deps api web ingestion
docker compose logs --tail=100 ingestion
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8000/api/v1/ingestion/status
.venv/bin/python scripts/verify_recovery.py --seconds 180
```

The verifier requires fresh successful writes, increasing retained count/checkpoint, and no new processing errors/reconnections during the observation. Retention/deletions may require manual interpretation of a count-based failure. An already expired cursor requires supported historical recovery; do not clear its flag or jump to now. A deterministic hold requires the review below. A green container alone is insufficient.

5. Once ingestion is stable, resume analysis with bounded catch-up:

```bash
docker compose up -d --no-deps trends
docker compose logs --tail=100 trends
curl --fail http://localhost:8000/api/v1/trending/status
curl --fail 'http://localhost:8000/api/v1/trending/popular?window=5'
.venv/bin/python scripts/verify_recovery.py --seconds 180 --require-trends
docker compose run --rm --no-deps api python -m trendsky_api.operations
```

Watch backlog, processing/query duration, heartbeat and ingestion throughput together. `TRENDS_BATCH_SIZE` and `TRENDS_BATCH_PAUSE_SECONDS` bound catch-up; reduce batch size/increase pause if necessary, rather than dropping jobs. Never truncate the queue. Insufficient covered history must still yield unavailable comparisons.

6. Record the checkpoint, run a controlled `docker compose restart ingestion`, and repeat the 180-second verifier after reconnect/catch-up settles. Verify the inclusive cursor advances, duplicates do not inflate counts, and no error loop returns. Inspect homepage/trending, mobile layout, search URL and artwork in the real deployment. Restart/recovery and sustained **production** observation are not executed in this session.

### Reviewing a deterministic hold

Stop only ingestion before acknowledging a hold. Inspect the safe `persistence_fault` and JSON logs by batch ID. Establish that the specific validation/schema/code defect is repaired. Capture the exact `last_error` marker and `last_seq` locally using a restricted database session. Review the corresponding coverage gap and replay availability. The marker contains only structural metadata and sequence bounds, not recoverable event content.

In a transaction with a short lock timeout, an operator may clear **only the exact reviewed marker**, leaving `last_seq` unchanged:

```sql
BEGIN;
SET LOCAL lock_timeout = '1s';
SELECT source_id, last_seq, last_error FROM ingestion_state
WHERE source_id = 'bluesky' FOR UPDATE;
UPDATE ingestion_state SET last_error = NULL, status = 'interrupted', connected_at = NULL
WHERE source_id = 'bluesky' AND last_error = 'EXACT_REVIEWED_BLOCKED_MARKER';
-- Require exactly one updated row and the same checkpoint; otherwise ROLLBACK.
COMMIT;
```

The sentinel must be replaced with the complete reviewed `blocked|...` value; never use a broad wildcard or clear `cursor_expired`. This is a manual acknowledgement, not a repair for an unknown failure. Retain the gap/incident evidence. Restart ingestion and verify replay; if the same fault returns, retain the hold and investigate. Historical backfill remains an operator workflow, not automatic checkpoint skipping.

## Reproducing isolated validation

```bash
# TEST_DATABASE_URL must identify an empty disposable PostgreSQL database, never TrendSky data.
TEST_DATABASE_URL='postgresql+psycopg://USER@HOST/DISPOSABLE_DB' .venv/bin/pytest tests/api -q
TEST_DATABASE_URL='postgresql+psycopg://USER@HOST/DISPOSABLE_DB' .venv/bin/python scripts/benchmark_recovery_postgres.py --confirm-disposable --posts 25000 --storage-description 'describe measured host/storage' --output /tmp/trendsky-pg-benchmark.json
npm test
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

## Acceptance remaining incomplete

Docker socket access is denied and `sudo -n` requires authentication. We did not repeatedly retry privileged commands. Operational container build/start, deployed revision/catalog inspection, real repaired ingestion persistence, sustained collection, controlled operational restart, production queue drain/rankings and frontend-to-live-data acceptance remain **Blocked**. The zero-byte backup must be replaced. This milestone is not marked recovered/complete. No Milestone 4 work was started.

Preventive priorities: deploy these diagnostics, validate automated backups by isolated restores, alert on lag/error/cursor holds and trend freshness separately, and measure production WAL/checkpoint/IO under real load before changing database settings.
