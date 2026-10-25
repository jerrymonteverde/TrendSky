# Data dictionary — foundation

`data_sources` records configuration, not collection evidence.

| Column | SQL type | Meaning |
| --- | --- | --- |
| id | varchar(32), primary key | Stable source key; `bluesky` |
| name | varchar(100), not null | Display name |
| collection_status | varchar(20), not null, check constrained | `not_started`, `collecting`, `paused`; seeded `not_started` |
| created_at | timestamp with time zone, server default | UTC-aware source registration time, **not** collection start |

Alembic revision `0001_sources` creates one source row. Re-running upgrade is idempotent; downgrade removes the table. No posts, contributors, topics, events or forecasts are stored. ORM metadata is compared with migrated schema in tests.

The collection-summary API deliberately exposes null collection timestamps and counts. No collection process exists to update these values. Coverage and analytical tables will be designed alongside ingestion rather than pre-populated speculatively.
