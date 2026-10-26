"""Optional PostgreSQL contract in a fresh test schema, never the operational database."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, select, text
from trend_fixtures import seed_scenarios
from trendsky_api.config import Settings
from trendsky_api.ingestion.protocol import JetstreamEvent
from trendsky_api.ingestion.store import IngestionStore
from trendsky_api.models import Post
from trendsky_api.trends.extraction import topic
from trendsky_api.trends.models import TrendSnapshot
from trendsky_api.trends.processor import aggregate_query, process_batch, refresh


@pytest.mark.postgres
def test_postgresql_grouping_sets_trigger_and_recovery(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL must point to a disposable PostgreSQL database")
    schema = "trend_contract_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-c search_path={schema}"})
    try:
        monkeypatch.setattr("trendsky_api.database.get_engine", lambda: engine)
        command.upgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "head")
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        asof = now - timedelta(minutes=1)
        seed_scenarios(engine, asof, now)
        settings = Settings(_env_file=None)
        while process_batch(engine, settings, now):
            pass
        refresh(engine, settings, now)
        with engine.begin() as connection:
            value = connection.execute(
                select(TrendSnapshot.metrics).where(
                    TrendSnapshot.topic_id == topic("hashtag", "rocket").id,
                    TrendSnapshot.window_minutes == 5,
                    TrendSnapshot.language == "all",
                )
            ).scalar_one()
            assert value["current_activity"] == 20 and value["growth_percent"] == 150
            query = aggregate_query(connection, asof - timedelta(minutes=40), asof, 5, settings)
            plan = str(query.compile(engine, compile_kwargs={"literal_binds": True}))
            assert connection.exec_driver_sql(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + plan
            ).scalar_one()
            connection.execute(delete(Post).where(Post.rkey == "rocket-0-0"))
            assert (
                connection.execute(
                    select(TrendSnapshot.topic_id).where(
                        TrendSnapshot.topic_id == topic("hashtag", "rocket").id
                    )
                ).first()
                is None
            )
        IngestionStore(engine).persist_batch(
            [
                JetstreamEvent(
                    seq=10000000,
                    event_at=now,
                    kind="commit",
                    did="did:plc:abcdefghijklmnopqrstuvwx",
                    operation="create",
                    rkey="nul",
                    record={
                        "text": "public\x00text #nul",
                        "createdAt": now.isoformat(),
                        "langs": ["en"],
                    },
                )
            ],
            None,
        )
        with engine.connect() as connection:
            assert (
                connection.execute(select(Post.text).where(Post.rkey == "nul")).scalar_one()
                == "public\ufffdtext #nul"
            )
        while process_batch(engine, settings, now):
            pass
        refresh(engine, settings, now)
        assert process_batch(engine, settings, now) == 0
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
