"""PostgreSQL-specific recovery fixtures use only the explicitly disposable TEST_DATABASE_URL."""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from trendsky_api.config import Settings
from trendsky_api.ingestion.failures import PersistenceBlocked, parse_failure
from trendsky_api.ingestion.protocol import JetstreamEvent
from trendsky_api.ingestion.store import IngestionStore
from trendsky_api.ingestion.text import RecordValidationError
from trendsky_api.ingestion.worker import RateWindow, _persist_batch
from trendsky_api.models import Hashtag, IngestionState, Post
from trendsky_api.operations import inspect
from trendsky_api.trends.models import TopicJob
from trendsky_api.trends.processor import process_batch

pytestmark = pytest.mark.postgres


@pytest.fixture
def recovery_pg(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL TEST_DATABASE_URL not configured")
    schema = "recovery_" + uuid.uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"options": f"-c search_path={schema} -c lock_timeout=100ms"},
    )
    monkeypatch.setattr("trendsky_api.database.get_engine", lambda: engine)
    command.upgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "head")
    yield engine, admin
    engine.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


def sample(seq=1, operation="create", value="public\x00text 日本語 💙 #valid"):
    return JetstreamEvent(
        seq,
        datetime.now(UTC),
        "commit",
        "did:plc:abcdefghijklmnopqrstuvwx",
        operation,
        "fixture",
        {
            "text": value,
            "langs": ["en\x00", "es"],
            "facets": [
                {"features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "facet\x00tag"}]}
            ],
        }
        if operation != "delete"
        else None,
    )


def test_postgres_nul_facet_and_json_metadata_are_storable_atomically(recovery_pg):
    engine, _ = recovery_pg
    store = IngestionStore(engine)
    store.persist_batch([sample()], None)
    with engine.connect() as connection:
        row = connection.execute(select(Post.__table__)).mappings().one()
        assert row["text"] == "public\ufffdtext 日本語 💙 #valid"
        assert row["languages"] == ["en\ufffd", "es"]
        assert "facet\ufffdtag" in set(connection.execute(select(Hashtag.tag)).scalars())
        assert connection.execute(select(TopicJob.generation)).scalar_one() == 1
    assert store.load_state()["last_seq"] == 1
    assert store.persist_batch([sample()], None)["duplicates"] == 1
    store.persist_batch([sample(2, "update")], None)
    store.persist_batch([sample(3, "delete")], None)
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Post)).scalar_one() == 0
        assert connection.execute(select(TopicJob.generation)).scalar_one() == 3
    assert process_batch(engine, Settings(_env_file=None)) == 1
    assert process_batch(engine, Settings(_env_file=None)) == 0


def test_postgres_bad_length_rolls_back_valid_prefix_and_checkpoint(recovery_pg):
    engine, _ = recovery_pg
    store = IngestionStore(engine)
    with pytest.raises(RecordValidationError):
        store.persist_batch([sample(1), sample(2, value="#" + "ß" * 127)], None)
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Post)).scalar_one() == 0
        assert connection.execute(select(func.count()).select_from(TopicJob)).scalar_one() == 0
    assert store.load_state()["last_seq"] is None


def test_actual_lock_timeout_is_retried_without_losing_transaction(recovery_pg, monkeypatch):
    engine, _ = recovery_pg
    store = IngestionStore(engine)
    lock = engine.connect()
    lock.begin()
    lock.execute(select(IngestionState.source_id).with_for_update()).all()
    real_sleep = asyncio.sleep
    retries = []

    async def release_before_retry(delay):
        retries.append(delay)
        lock.rollback()
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", release_before_retry)
    try:
        asyncio.run(_persist_batch(store, [sample()], RateWindow(), 100))
    finally:
        lock.close()
    assert len(retries) == 1
    assert store.load_state()["last_seq"] == 1


def test_stale_pool_connection_reconnects_to_actual_postgres(recovery_pg):
    engine, admin = recovery_pg
    with engine.connect() as connection:
        pid = connection.execute(select(func.pg_backend_pid())).scalar_one()
    with admin.begin() as connection:
        assert connection.execute(select(func.pg_terminate_backend(pid))).scalar_one()
    IngestionStore(engine).persist_batch([sample()], None)
    assert IngestionStore(engine).load_state()["last_seq"] == 1


def test_actual_constraint_failure_blocks_without_partial_queue_or_checkpoint(recovery_pg):
    engine, _ = recovery_pg
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE posts ADD CONSTRAINT synthetic_rejection "
                "CHECK (text <> 'synthetic rejected observation')"
            )
        )
    store = IngestionStore(engine)
    with pytest.raises(PersistenceBlocked) as failure:
        asyncio.run(
            _persist_batch(
                store,
                [sample(1), sample(2, value="synthetic rejected observation")],
                RateWindow(),
                100,
            )
        )
    assert failure.value.safe_info.sqlstate == "23514"
    assert failure.value.safe_info.phase == "posts"
    assert parse_failure(store.load_state()["last_error"]).blocked
    assert store.load_state()["last_seq"] is None
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Post)).scalar_one() == 0
        assert connection.execute(select(func.count()).select_from(TopicJob)).scalar_one() == 0


def test_diagnostics_are_read_only_and_exclude_observation_content(recovery_pg):
    engine, _ = recovery_pg
    IngestionStore(engine).persist_batch([sample(value="private synthetic observation")], None)
    report = inspect(engine)
    assert report["schema"] == [{"version_num": "0003_trends"}]
    assert report["counts"][0]["retained_posts"] == 1
    assert "private synthetic observation" not in str(report)
    assert "unavailable" not in report["checkpoint_cluster_counters"]
