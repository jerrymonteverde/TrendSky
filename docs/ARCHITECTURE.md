# Architecture

## Implemented boundaries

- `apps/web`: Next.js App Router, server pages and small client interaction components. Only the server calls the internal API URL. No database secrets enter the browser bundle.
- `apps/api`: FastAPI, Pydantic contracts, a bounded in-process limiter, explicit CORS and SQLAlchemy connectivity.
- `apps/api/migrations`: Alembic schema lifecycle. A separate Compose job gates API startup.
- `infrastructure`: container build definitions, database bootstrap and optional Caddy ingress.
- `tests`: deterministic API/migration tests and browser interaction tests.

PostgreSQL is the operational database. The current schema contains source configuration only. `GET /api/v1/live` is process liveness. `GET /api/v1/health` returns 200 only when connectivity, the source seed and migration revision are ready; failures return safe 503 responses. `GET /api/v1/analytics/summary` returns a foundation collection contract. Unknown data counts and timestamps are null, never fabricated zeroes.

The web server has a 2.5-second API timeout and shows an explicit unavailable state on failures or unexpected payloads. Status requests are not cached. Client interactions stay disabled until hydration, preventing early clicks from being lost. Query input is bounded to 120 characters, whitespace-normalized, URI-encoded and rendered as text through React.

## Deferred boundaries

Production builds use Next.js's supported webpack builder. Turbopack remains the development default, with `127.0.0.1` explicitly allowed as a local development origin. This environment blocked Turbopack CSS-worker sockets during a fresh production rebuild, including an elevated retry; webpack avoids that environment-specific build path.

Ingestion, trend aggregation, historical processing, training and inference will be separate workers/modules. Spark and model training will never run in HTTP handlers. Website availability will not depend on Databricks or successful model training. No empty worker directories or unused analytical dependencies have been added.

## Dependency decision

Resolved on 2026-10-24 using npm/PyPI metadata and official [Next.js](https://nextjs.org/docs/app/getting-started/installation), [FastAPI](https://fastapi.tiangolo.com/deployment/docker/), [SQLAlchemy](https://docs.sqlalchemy.org/en/21/), [Pydantic](https://docs.pydantic.dev/latest/) and [shadcn/ui](https://ui.shadcn.com/docs/installation/next) documentation. Registry metadata confirmed Next 16.4.3 accepts React 19 and Node >=20.9; Node 22 is used. Installed Python packages support the local Python 3.14 runtime. PostgreSQL 18 is a stable supported release; no release candidate was chosen. Locks record exact resolutions; container base tags receive compatible patches and are not digest-pinned. Image build verification is separately tracked.
