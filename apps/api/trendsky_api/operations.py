"""Read-only, bounded PostgreSQL diagnostics: python -m trendsky_api.operations."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, create_engine, text

from trendsky_api.config import get_settings
from trendsky_api.observability import safe_error

# No SQL text from pg_stat_activity, row content, DIDs, connection strings or passwords.
QUERIES = {
    "database": "SELECT current_setting('server_version') AS version, "
    "pg_database_size(current_database()) AS bytes, "
    "current_setting('shared_buffers') AS shared_buffers, "
    "current_setting('max_connections') AS max_connections, "
    "current_setting('checkpoint_timeout') AS checkpoint_timeout, "
    "current_setting('max_wal_size') AS max_wal_size",
    "schema": "SELECT version_num FROM alembic_version",
    "relations": "SELECT relname, n_live_tup, n_dead_tup, "
    "pg_table_size(relid) AS table_bytes, pg_indexes_size(relid) AS index_bytes, "
    "last_autovacuum, last_autoanalyze FROM pg_stat_user_tables "
    "WHERE schemaname = current_schema() ORDER BY pg_total_relation_size(relid) DESC",
    "connections": "SELECT state, wait_event_type, wait_event, count(*) AS connections, "
    "max(extract(epoch FROM clock_timestamp() - xact_start)) AS max_transaction_seconds "
    "FROM pg_stat_activity WHERE datname = current_database() "
    "GROUP BY state, wait_event_type, wait_event",
    "locks": "SELECT mode, granted, count(*) FROM pg_locks "
    "WHERE database = (SELECT oid FROM pg_database WHERE datname = current_database()) "
    "GROUP BY mode, granted",
    "wal_cluster_counters": "SELECT wal_records, wal_fpi, wal_bytes, wal_buffers_full, "
    "stats_reset FROM pg_stat_wal",
    "checkpoint_cluster_counters": "SELECT num_timed, num_requested, write_time, sync_time, "
    "buffers_written, stats_reset FROM pg_stat_checkpointer",
    "database_counters": "SELECT xact_commit, xact_rollback, deadlocks, temp_bytes, "
    "blk_read_time, blk_write_time, stats_reset FROM pg_stat_database "
    "WHERE datname = current_database()",
    "counts": "SELECT (SELECT count(*) FROM posts) AS retained_posts, "
    "(SELECT count(*) FROM topic_jobs) AS pending_jobs, "
    "(SELECT count(*) FROM trend_snapshots) AS snapshots",
    "ingestion": "SELECT status, last_seq, last_event_at, last_persisted_at, heartbeat_at, "
    "processing_errors, cursor_expired FROM ingestion_state WHERE source_id = 'bluesky'",
    "trends": "SELECT status, heartbeat_at, last_calculated_at, backlog, posts_processed, "
    "errors, processing_ms, query_ms, ranking_ms FROM trend_state WHERE id = 'bluesky'",
}


def inspect(engine: Engine) -> dict[str, Any]:
    report: dict[str, Any] = {"observed_at": datetime.now(UTC).isoformat()}
    for name, sql in QUERIES.items():
        try:
            with engine.begin() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                connection.execute(text("SET LOCAL lock_timeout = '100ms'"))
                report[name] = [dict(row) for row in connection.execute(text(sql)).mappings()]
        except Exception as exc:
            report[name] = {"unavailable": asdict(safe_error(exc))}
    return report


def main() -> None:
    try:
        engine = create_engine(
            get_settings().sqlalchemy_url(),
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 3},
        )
        try:
            print(json.dumps(inspect(engine), default=str, indent=2))
        finally:
            engine.dispose()
    except Exception as exc:
        print(json.dumps({"unavailable": asdict(safe_error(exc))}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
