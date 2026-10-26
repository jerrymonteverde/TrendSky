"""Synthetic PostgreSQL benchmark in a disposable TEST_DATABASE_URL, never operational data."""

import argparse
import json
import os
import platform
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/api"))

from trend_fixtures import seed_scenarios  # noqa: E402
from trendsky_api import database  # noqa: E402
from trendsky_api.config import Settings  # noqa: E402
from trendsky_api.ingestion.protocol import JetstreamEvent  # noqa: E402
from trendsky_api.ingestion.store import IngestionStore  # noqa: E402
from trendsky_api.operations import inspect  # noqa: E402
from trendsky_api.trends.extraction import topic  # noqa: E402
from trendsky_api.trends.models import TopicJob, TrendSnapshot  # noqa: E402
from trendsky_api.trends.processor import aggregate_query, process_batch, refresh  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--posts", type=int, default=25000)
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--storage-description", default="Storage medium not verified")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ.get("TEST_DATABASE_URL")
    if not args.confirm_disposable or not url or not 250 <= args.posts <= 100000:
        parser.error(
            "Require disposable TEST_DATABASE_URL, --confirm-disposable and 250–100000 posts."
        )
    schema = "recovery_benchmark_" + uuid.uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        hide_parameters=True,
        pool_size=2,
        max_overflow=0,
        connect_args={"options": f"-c search_path={schema}"},
    )
    try:
        database.get_engine = lambda: engine
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        asof = now - timedelta(minutes=1)
        seed_count = seed_scenarios(engine, asof, now)
        settings = Settings(_env_file=None)
        store = IngestionStore(engine)
        latencies = []
        for start in range(0, args.posts, 250):
            events = []
            for i in range(start, min(args.posts, start + 250)):
                activity = asof - timedelta(seconds=1 + i % 7200)
                events.append(
                    JetstreamEvent(
                        seq=1000000 + i,
                        event_at=now,
                        kind="commit",
                        did=f"did:synthetic:benchmark{i % 300}",
                        operation="create",
                        rkey=f"bench{i}",
                        record={
                            "text": f"#bench{i % 50} synthetic public conversation",
                            "createdAt": activity.isoformat(),
                            "langs": ["en" if i % 2 else "es"],
                        },
                    )
                )
            started = time.perf_counter()
            store.persist_batch(events, None)
            latencies.append((time.perf_counter() - started) * 1000)
        with engine.connect() as connection:
            initial_backlog = connection.execute(
                select(func.count()).select_from(TopicJob)
            ).scalar_one()
        processed = 0
        extraction_started = time.perf_counter()
        while count := process_batch(engine, settings, now):
            processed += count
        extraction_ms = (time.perf_counter() - extraction_started) * 1000
        refresh_started = time.perf_counter()
        timings = refresh(engine, settings, now)
        refresh_ms = (time.perf_counter() - refresh_started) * 1000
        assert process_batch(engine, settings, now) == 0
        with engine.connect() as connection:
            rocket = connection.execute(
                select(TrendSnapshot.metrics).where(
                    TrendSnapshot.topic_id == topic("hashtag", "rocket").id,
                    TrendSnapshot.window_minutes == 5,
                    TrendSnapshot.language == "all",
                )
            ).scalar_one()
            assert rocket["current_activity"] == 20 and rocket["growth_percent"] == 150
            query = aggregate_query(connection, asof - timedelta(minutes=40), asof, 5, settings)
            sql = str(query.compile(engine, compile_kwargs={"literal_binds": True}))
            plan = connection.exec_driver_sql(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
            ).scalar_one()
        report = {
            "dataset": "Synthetic, isolated; no operational observations",
            "environment": args.storage_description,
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "posts_ingested": args.posts,
            "scenario_posts_seeded": seed_count,
            "batch_size": 250,
            "batches": len(latencies),
            "batch_latency_ms": {
                "median": statistics.median(latencies),
                "p95": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
                "max": max(latencies),
            },
            "ingestion_posts_per_second": args.posts / (sum(latencies) / 1000),
            "queue_initial": initial_backlog,
            "queue_processed": processed,
            "extraction_ms": extraction_ms,
            "refresh_ms": refresh_ms,
            "refresh_windows": timings,
            "representative_aggregate_plan": plan,
            "diagnostics": inspect(engine),
            "ranking_validation": {
                "rocket_activity": rocket["current_activity"],
                "rocket_growth_percent": rocket["growth_percent"],
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
        print(
            json.dumps(
                {
                    key: value
                    for key, value in report.items()
                    if key not in {"representative_aggregate_plan", "diagnostics"}
                },
                default=str,
            )
        )
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


if __name__ == "__main__":
    main()
