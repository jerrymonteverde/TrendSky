"""Validate the actual trend processor on isolated synthetic SQLite observations.

Never connects to the operational database. Writes an optional JSON evidence artifact.
"""

import argparse
import json
import os
import platform
import resource
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, insert, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "api"))

from trend_fixtures import seed_scenarios  # noqa: E402
from trendsky_api import database  # noqa: E402
from trendsky_api.config import Settings  # noqa: E402
from trendsky_api.models import CoverageGap, Post  # noqa: E402
from trendsky_api.trends.extraction import topic  # noqa: E402
from trendsky_api.trends.models import TrendSnapshot  # noqa: E402
from trendsky_api.trends.processor import aggregate_query, process_batch, refresh  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--posts", type=int, default=25000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings(_env_file=None)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    asof = now - timedelta(minutes=1)
    with tempfile.TemporaryDirectory(prefix="trendsky-validation-") as work:
        engine = create_engine(f"sqlite:///{work}/validation.db")
        database.get_engine = lambda: engine
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        count = seed_scenarios(engine, asof, now)
        fillers = max(0, args.posts - count)
        for batch_start in range(0, fillers, 500):
            rows = []
            for i in range(batch_start, min(fillers, batch_start + 500)):
                activity = asof - timedelta(seconds=1 + i % 7200)
                rows.append(
                    {
                        "uri": f"at://synthetic/load/{i}",
                        "rkey": f"load{i}",
                        "did": f"did:synthetic:load{i % 300}",
                        "text": "#syntheticload benchmark conversations",
                        "languages": ["en"],
                        "created_at": activity,
                        "event_at": activity,
                        "ingested_at": now,
                        "event_seq": 1000000 + i,
                    }
                )
            with engine.begin() as connection:
                connection.execute(insert(Post), rows)
        count += fillers
        started = time.perf_counter()
        processed = 0
        while batch := process_batch(engine, settings, now):
            processed += batch
        extraction_ms = (time.perf_counter() - started) * 1000
        timings = refresh(engine, settings, now)

        def metrics(label):
            with engine.connect() as connection:
                return connection.execute(
                    select(TrendSnapshot.metrics).where(
                        TrendSnapshot.topic_id == topic("hashtag", label).id,
                        TrendSnapshot.window_minutes == 5,
                        TrendSnapshot.language == "all",
                    )
                ).scalar_one()

        actual = {name: metrics(name) for name in ("steady", "rocket", "declining", "newtopic")}
        assert actual["steady"]["current_activity"] == 12
        assert actual["rocket"]["growth_percent"] == 150
        assert actual["declining"]["current_activity"] == 4
        assert actual["newtopic"]["growth_percent"] is None
        with engine.begin() as connection:
            connection.execute(
                delete(Post).where(Post.rkey.in_([f"deletedtopic-0-{i}" for i in range(3)]))
            )
        while process_batch(engine, settings, now):
            pass
        refresh(engine, settings, now)
        deleted = metrics("deletedtopic")
        assert deleted["current_activity"] == 5 and deleted["growth_percent"] == -37.5
        with engine.begin() as connection:
            connection.execute(
                insert(CoverageGap).values(
                    source_id="bluesky",
                    detected_at=asof - timedelta(minutes=2),
                    gap_start_at=asof - timedelta(minutes=3),
                    reason="synthetic_missing_interval",
                )
            )
        refresh(engine, settings, now)
        missing = metrics("rocket")
        assert missing["growth_percent"] is None and not missing["comparison_valid"]
        with engine.connect() as connection:
            query = aggregate_query(connection, asof - timedelta(minutes=40), asof, 5, settings)
            sql = str(query.compile(engine, compile_kwargs={"literal_binds": True}))
            plan = [row[3] for row in connection.exec_driver_sql("EXPLAIN QUERY PLAN " + sql)]
        report = {
            "dataset": "deterministic synthetic observations; no live Bluesky data",
            "database": "SQLite",
            "posts_seeded": count,
            "posts_extracted": processed,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "logical_cpus": os.cpu_count(),
            "peak_rss_kib_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "extraction_ms": round(extraction_ms, 3),
            "window_refresh_timings": timings,
            "scenario_metrics": {
                name: {
                    key: value[key]
                    for key in (
                        "current_activity",
                        "previous_activity",
                        "unique_contributors",
                        "growth_percent",
                        "trend_status",
                        "coverage_status",
                    )
                }
                for name, value in actual.items()
            },
            "deletion_correction": {
                "current_activity": deleted["current_activity"],
                "growth_percent": deleted["growth_percent"],
            },
            "missing_coverage": {
                "growth_percent": missing["growth_percent"],
                "coverage_status": missing["coverage_status"],
            },
            "sqlite_query_plan": plan,
            "postgres_explain_analyze": "not executed: operational Docker database inaccessible",
        }
        encoded = json.dumps(report, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded + "\n")
        print(encoded)
        engine.dispose()


if __name__ == "__main__":
    main()
