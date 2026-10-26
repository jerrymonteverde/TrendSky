# Implementation status

Last updated: 2026-10-25 (America/Hermosillo). Allowed statuses: Not Started, In Progress, Implemented, Tested, Blocked.

Milestone 3.1 is **In Progress**. The NUL-bearing explicit hashtag defect is reproduced and repaired on isolated PostgreSQL 18. Operational recovery is **Blocked** by Docker permissions; no operational database or checkpoint was modified. The final read-only API observation at **2026-10-26 04:55:05 UTC** still showed 167,331 retained posts, cursor `26446992220`, reconnecting ingestion, and stale trends. The repair is not deployed. The existing backup file is zero bytes and must not be treated as a valid backup.

| Milestone 3.1 deliverable | Status | Evidence / limit |
| --- | --- | --- |
| Root cause reproduction | Tested | Read-only stalled-cursor replay found NUL in an explicit hashtag facet; synthetic equivalent failed on PostgreSQL 18 before repair |
| PostgreSQL text/metadata compatibility | Tested | Post text, hashtag facets, language JSON, valid multilingual Unicode and malformed scalar handling |
| Transaction/queue/checkpoint integrity | Tested | Actual PG replay, updates/deletes, rollback after constraint failure and unchanged cursor/jobs |
| Safe error observability | Tested | JSON allowlist, SQLSTATE/static messages, correlation/phase/attempt, safe stack locations; no SQL parameters or exception text |
| Deterministic fault handling | Tested | Durable operator hold, coverage record, no skipped events/checkpoint reset, restart respects hold |
| Transient connection/transaction recovery | Tested | Actual PG lock timeout/retry and terminated pooled connection recovery; deterministic fixtures for worker reconnection/shutdown |
| Separate ingestion/trend/database health | Tested | Recent commit and heartbeat gates; stale rates hidden; stopped/delayed analysis cannot serve current rankings; readiness distinguishes degraded schema |
| Bounded trend catch-up | Tested | 25,436 synthetic PG queue jobs drained, no-op replay; configurable inter-batch pause |
| Backend regression suite | Tested | 84 passed, with real disposable PostgreSQL contracts enabled |
| Frontend regression checks | Tested | 22 unit tests, 26 desktop/mobile browser tests, ESLint, TypeScript and production build passed |
| Python quality / Compose validation | Tested | Ruff lint/format, strict mypy, diff whitespace and `docker compose config --quiet` passed |
| PostgreSQL measurements | Tested | 25,000 synthetic writes; median/p95 148.97/416.90 ms per 250; 30.74 s queue drain; 3.51 s refresh; actual EXPLAIN/BUFFERS/catalog artifact |
| Production backup / catalog inspection | Blocked | Zero-byte existing archive; Docker daemon denied; operational sizes/WAL/locks/IO not measured |
| Production ingestion/trend restoration | Blocked | Images not deployed; no sustained repaired live collection or controlled operational restart verified |
| Recovery runbook and incident report | Implemented | [Recovery report](MILESTONE-3.1-RECOVERY-REPORT.md), [analysis](INGESTION-INCIDENT-ANALYSIS.md), read-only diagnostics and sustained verifier |
| Milestone 4 | Not Started | No new product/analytical feature or redesign |

The table below preserves **historical Milestone 3 implementation evidence** from the preceding execution. Its older operational observations and SQLite-only measurements are not the current recovery status.

| Deliverable | Status | Evidence / limit |
| --- | --- | --- |
| Existing illustrated product and ingestion | In Progress | Initially observed collecting; final check found 86,856 retained posts with the collector reconnecting and stalled at 03:00 UTC |
| Source text PostgreSQL compatibility | Tested | Replay sample found six NUL-containing posts; persistence now replaces NUL with U+FFFD and advances the batch atomically. Live recovery awaits image deployment |
| Deterministic hashtag/keyword/phrase extraction | Tested | Unicode, English/Spanish stopwords, declared/unknown languages, duplicates, facet tags, URL/spam filtering and phrase boundaries |
| Incremental source change capture | Tested | SQLite migration triggers queue inserts/edits/deletes, preserve existing source rows, and invalidate/recompute affected derived results |
| SQL window aggregation | Tested | Five window sizes, source event placement, exact contributors across languages, half-open boundaries, late arrivals, replay and retention correction |
| Growth, acceleration, robust baseline and momentum | Tested | Formula, threshold, zero-baseline, partial-coverage and single-author scenarios |
| Popular / Rising / Emerging ranking snapshots | Tested | Deterministic SQL/statistical pipeline and stable API ordering; snapshot freshness checked |
| Ingestion-aware coverage quality | Tested | Complete/partial/missing-history windows; missing history chart points remain null |
| Migration `0003_trends` | Tested | SQLite upgrade/down/up/schema parity and source-record preservation; operational PostgreSQL not migrated here |
| Read-only trend/topic APIs | Tested | Valid/invalid filters, pagination, empty data, topic details, stale results and source-deletion invalidation |
| Python suite | Tested | 49 passed; two PostgreSQL-only contracts skipped without disposable `TEST_DATABASE_URL` |
| Frontend unit suite | Tested | 19 passed, including measured cards, transport, exact artwork aliases and null-aware sparklines |
| Responsive browser regressions | Tested | 26 desktop/mobile Chromium checks passed; trend filters, summaries, images, themes, navigation and overflow |
| Frontend lint/type/build | Tested | ESLint, TypeScript and standalone Next.js production build |
| Python quality | Tested | Ruff check/format and mypy |
| Synthetic performance evidence | Tested | 25,000 source fixtures processed; measured timings, RSS and SQLite query plan in `docs/evidence/milestone-3-synthetic.json` |
| Dedicated trends Compose service | Implemented | No host port; 384 MiB, 0.5 CPU; migration-success gate; config validation passes |
| Live PostgreSQL trigger/query/worker acceptance | Blocked | Docker socket access denied, noninteractive sudo requires authentication; no live Milestone 3 rankings claimed |
| Methodology, data dictionary and report | Implemented | Formulas, correction strategy, limits, run commands, actual tests and evidence |
| Milestone 4 full Explore/Compare | Not Started | Basic topic summaries only are included in Milestone 3 |
| Spark/Databricks/ML/LLM features | Not Started | No unused analytical dependencies introduced |

## Remaining acceptance gate

On the Docker-authorized host, follow the backup-first sequence in [MILESTONE-3.1-RECOVERY-REPORT.md](MILESTONE-3.1-RECOVERY-REPORT.md). No new migration is needed if the deployed revision is already `0003_trends`; inspect rather than downgrade/reseed. Confirm repaired ingestion, checkpoint progress, backlog drain and real rankings over sustained observation and a controlled worker restart. Record actual production results before marking recovery complete. Isolated PostgreSQL contracts and EXPLAIN measurements have now been executed; production load remains unmeasured.

The test-only browser API and SQLite validation fixtures never enter the public application. No synthetic result is presented as a live trend.
