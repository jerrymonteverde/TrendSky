# Ingestion incident analysis — Milestone 3.1

## Confirmed at initial audit

- The live API returned `reconnecting`, 167,331 stored posts, cursor `26446992220`, last event `2026-10-26T03:28:29.768269Z`, last persistence `03:51:38.208658Z`, and 67 processing errors. These are dated observations, not current guarantees.
- Trend status was `stale`, with its last calculation at `04:09:52.676724Z`. A stale ranking processor is distinct from the ingestion persistence failure.
- Docker API access is denied and noninteractive sudo requires authentication. Operational SQL, container logs and deployed schema inspection are blocked from this session.
- The existing `backups/trendsky-before-milestone3.dump` is **0 bytes**. It is not a valid backup. Local filesystem has about 304 GiB free; `/tmp` has about 3.3 GiB available. No operational migration or destructive operation is authorized by the presence of that file.
- Existing logging uses a plain formatter that omits `extra` fields. SQLSTATE, retry phase and correlation are therefore unavailable in current logs. SQLAlchemy exception strings can expose SQL parameters and must not be logged directly.
- All SQLAlchemy errors receive the same five retries. The outer connection loop then replays the unchanged checkpoint indefinitely, including deterministic errors.

## Persistence transaction trace

`IngestionStore.persist_batch()` opens one transaction and locks the source `ingestion_state` row on PostgreSQL. It deduplicates/sorts sequence numbers, folds multiple changes for a URI, then:

1. Records invalid sequenced-frame coverage warnings.
2. Deletes hashtag relationships and posts for account/sync tombstones or record deletes.
3. Upserts current posts, including text, declared-language JSON, timestamps and source sequence.
4. Inserts normalized hashtags, resolves their IDs, and replaces post–hashtag links.
5. Updates durable sequence, event/persistence timestamps and cumulative counters.
6. Updates the open collection period's sequence bound and commits.

Post insert/update/delete also invokes `trendsky_post_changed()` installed by `0003_trends`. That trigger updates topic revisions, invalidates applicable snapshots, removes obsolete mentions/orphan topics, and upserts `topic_jobs`. These operations remain active when the trends container is stopped. A failed transaction rolls back both post writes and the checkpoint.

## Hypotheses requiring evidence

- Unsupported values in fields other than `posts.text` (hashtags, metadata, identifiers), length/encoding errors, or JSON compatibility.
- Integrity/trigger/queue conflicts or deployed-schema mismatch.
- Transient connection, lock, disk/WAL/checkpoint or resource pressure.

The earlier NUL-in-post-text issue does not prove the cause of this later failure. A long PostgreSQL checkpoint and a point-in-time idle activity view do not independently establish the cause. PostgreSQL-specific reproduction and safe structured diagnostics are required before changing persistence or schema behavior.

## Investigation method

Use an isolated PostgreSQL 18 cluster with private local sockets and synthetic fixtures. Do not restore or modify operational data, reset its cursor, or bypass the failed record. Read-only Jetstream samples may retain only safe counts/types/sequence metadata, never post text, DIDs or credentials in reports. Findings below will distinguish reproduced defects from operational conclusions that still require host logs.

## Confirmed field-level failure

A read-only 500-frame replay starting at `26446992220` contained 468 post records. At frame index 14, sequence `26446992388`, both post text and an explicit hashtag facet contained NUL. The hashtag had 11 characters. No raw text, tag label or author identifier was retained in this report.

The current code replaces NUL only in `posts.text`. `hashtags_from_record()` accepts the facet string, and `persist_batch()` sends that unnormalized value to `hashtags.tag`. A synthetic event with the same field pattern reproduced SQLAlchemy `DataError` on an actual, isolated PostgreSQL **18.0** server. The underlying client adapter provided no SQLSTATE for this failure. The source row count, queue row count and checkpoint remained unchanged after rollback. This confirms a deterministic persistence defect consistent with the live stuck checkpoint, independently of the trends process.

Before changing persistence, the existing PostgreSQL migration and trend contracts passed (three checks including SQLite/PG migration variants). This does not prove every deployed schema detail matches or exclude separate operational I/O pressure. Operational logs and catalog statistics remain unavailable because Docker access is denied.

## Targeted repair decision

Normalize PostgreSQL-incompatible NUL/unpaired scalar values in supported post text, language JSON strings and hashtag metadata at persistence. Preserve valid Unicode/emoji. Validate stable identifiers instead of rewriting them. Unsupported lengths remain explicit deterministic failures requiring operator review, never silent truncation or cursor skipping. Use safe error classification, bounded transient retries and a durable blocked-failure marker in existing operational state; no new operational table or destructive migration is necessary.

## Repair verification and remaining boundary

The repaired synthetic NUL-bearing facet, text and language JSON commit together on PostgreSQL 18; inclusive replay does not add another post/job. Actual PostgreSQL tests also verify update/delete job generations, rollback after a real check-constraint failure, lock timeout retry and recovery of a terminated pooled connection. Full backend suite: 84 passed with PostgreSQL enabled. Frontend: 22 unit / 26 desktop-mobile browser checks passed, with production build/lint/types. Compose configuration validates without needing the daemon.

A separate 25,000-post synthetic PG benchmark measured median/p95 batch latency 148.97/416.90 ms, 30.74-second queue drain and 3.51-second five-window publication. The cluster uses tmpfs and no Compose CPU caps; production IO and table/index/lock statistics remain unknown. Neither these measurements nor the historical 270-second checkpoint establish an operational IO root cause.

At 2026-10-26 04:55:05 UTC the unchanged deployment still reported 167,331 posts, cursor `26446992220`, 97 processing errors and 118 reconnects; trends remained stale. See [safe API snapshot](evidence/milestone-3.1-live-status.json). This confirms the unmodified runtime still needs deployment; it is not a repaired-live test. No production mutation, cursor reset, migration or container restart was attempted. Recovery is **not complete**. Follow the [backup-first recovery runbook](MILESTONE-3.1-RECOVERY-REPORT.md), including sustained collection and controlled restart verification.
