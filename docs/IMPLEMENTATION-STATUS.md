# Implementation status

Last updated: 2026-10-24. Work is limited to Milestone 1.

**Milestone 1: Blocked — implementation and local application tests are finished; full Docker/PostgreSQL acceptance remains unverified.** Docker socket access is denied for this execution user. Elevated `docker info` was also denied; `sudo -n docker info` requires interactive authentication. No destructive permission or host configuration changes were attempted. The existing `.env` was preserved.

Allowed statuses: Not Started, In Progress, Implemented, Tested, Blocked.

| Deliverable | Status | Evidence / limit |
| --- | --- | --- |
| Monorepo on develop | Implemented | Web, API, infrastructure, tests, CI, docs; no push |
| Next.js production build | Tested | `npm run build` with webpack; standalone server started successfully |
| Five initial routes and homepage | Tested | Playwright desktop/mobile; original brand layout |
| Search redirect and query preservation | Tested | URL encoding, hashtag/phrase/Spanish query, reload, blank input |
| Light/dark themes | Tested | Light default; toggle and persisted reload |
| Responsive layouts | Tested | Desktop Chromium and mobile viewport overflow checks; not physical device certification |
| FastAPI | Tested | API contracts, CORS, error safety, rate limiting, liveness and HTTP failure behavior |
| Frontend/backend communication | Tested | Typed client tests; real API 503 visibly handled by web; healthy contract tested with fixtures |
| SQLAlchemy source registry | Tested | SQLite persistence fixtures; no conversation observations |
| Alembic migration | Tested | SQLite upgrade twice, seed, ORM/schema comparison, downgrade, re-upgrade |
| PostgreSQL configuration and restricted app role | Implemented | PostgreSQL 18 service and initialization SQL; not executed against PostgreSQL locally |
| PostgreSQL connection and migration acceptance | Blocked | PostgreSQL-specific test skipped without `TEST_DATABASE_URL`; CI job provided, not executed here |
| Compose configuration | Tested | `docker compose config --quiet` using ephemeral non-secret validation values |
| Docker image builds and full startup | Blocked | Docker socket permission; no successful container build/start claim |
| Caddy HTTPS | Implemented | Optional production profile; no deployment/TLS verification |
| Foundational automated tests | Tested | 7 TypeScript; 9 Python passed, 1 PostgreSQL test skipped; 14 browser tests passed against development and again against production standalone |
| Dependency audits | Tested | npm and pinned Python runtime audit: no known vulnerabilities at time of execution |
| GitHub Actions | Implemented | Lint/type/unit/browser/PostgreSQL/Docker/audit jobs; remote workflow not run |
| README and engineering docs | Implemented | Run instructions, architecture, design, dictionary, limitations and report |

## Remaining acceptance gate

On a Docker-capable host: merge `.env.example` settings, supply distinct database secrets, run `docker compose up --build -d --wait --wait-timeout 180`, then `python3 scripts/smoke.py`. Execute the PostgreSQL migration contract against a disposable database. Confirm Caddy separately if using the production profile. Only then mark Docker/PostgreSQL acceptance Tested and Milestone 1 fully verified.

## Roadmap

| Milestone | Status |
| --- | --- |
| 1 — Foundation | Blocked |
| 2 — Bluesky ingestion | Not Started |
| 3 — Trend detection | Not Started |
| 4 — Explore and Compare analytics | Not Started |
| 5 — Data engineering | Not Started |
| 6 — Machine learning | Not Started |
| 7 — Advanced analytics | Not Started |
| 8 — MLOps and experimentation | Not Started |
| 9 — Production and portfolio | Not Started |

No ingestion service was started. No charts, historical data, trend scores, forecasts, cloud jobs or fabricated datasets are presented as implemented.
