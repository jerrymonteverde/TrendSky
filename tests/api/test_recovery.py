import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DataError, OperationalError
from test_ingestion_store import event, make_store
from trendsky_api.config import Settings
from trendsky_api.ingestion.failures import BatchFailure, PersistenceBlocked, parse_failure
from trendsky_api.ingestion.text import postgres_text
from trendsky_api.ingestion.worker import RateWindow, _persist_batch, run_worker
from trendsky_api.models import IngestionState, Post


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Español 日本語 💙", "Español 日本語 💙"),
        ("a\x00b", "a\ufffdb"),
        ("a\ud800b", "a\ufffdb"),
        ("\ud83d\ude00", "😀"),
    ],
)
def test_pg_text_preserves_valid_unicode_and_normalizes_only_unsupported_scalars(value, expected):
    assert postgres_text(value) == expected


def test_deterministic_failure_is_durable_and_not_retried(monkeypatch):
    engine, store = make_store()
    original = store.persist_batch
    store.persist_batch = Mock(
        side_effect=DataError("private SQL", {}, ValueError("private value"))
    )

    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", inline)
    with pytest.raises(PersistenceBlocked) as failure:
        asyncio.run(_persist_batch(store, [event(12)], RateWindow(), 100))
    assert store.persist_batch.call_count == 1
    state = store.load_state()
    marker = parse_failure(state["last_error"])
    assert marker == failure.value.failure
    assert marker.blocked and marker.seq_min == 12
    assert state["status"] == "error" and state["last_seq"] is None
    assert store.status_snapshot(60)["health"] == "persistence_failure"
    assert len(state["last_error"]) <= 160
    store.persist_batch = original
    engine.dispose()


def test_transient_failure_retries_then_commits_once(monkeypatch):
    engine, store = make_store()
    persist = store.persist_batch
    driver = Exception("private connection string")
    driver.sqlstate = "08006"
    store.persist_batch = Mock(
        side_effect=[OperationalError("secret", {}, driver), {"posts_written": 1}]
    )

    async def inline(function, *args, **kwargs):
        if function == store.persist_batch and store.persist_batch.call_count:
            return persist(*args, **kwargs)
        return function(*args, **kwargs)

    async def no_delay(_):
        return None

    monkeypatch.setattr(asyncio, "to_thread", inline)
    monkeypatch.setattr(asyncio, "sleep", no_delay)
    asyncio.run(_persist_batch(store, [event(12)], RateWindow(), 100))
    assert store.load_state()["last_seq"] == 12
    with engine.connect() as connection:
        assert connection.execute(select(Post.event_seq)).scalar_one() == 12
    engine.dispose()


def test_worker_restart_respects_blocked_marker_without_reconnecting(monkeypatch):
    engine, store = make_store()
    failure = BatchFailure("a" * 12, 1, 12, 12, "data", None, "hashtags")
    store.record_batch_failure(failure)
    connect = Mock(side_effect=AssertionError("must not connect"))

    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", inline)

    async def run():
        stop = asyncio.Event()
        worker = asyncio.create_task(run_worker(store, Settings(_env_file=None), stop, connect))
        await asyncio.sleep(0.02)
        stop.set()
        await asyncio.wait_for(worker, 1)

    asyncio.run(run())
    connect.assert_not_called()
    assert parse_failure(store.load_state()["last_error"]) == failure
    assert store.load_state()["last_seq"] is None
    engine.dispose()


def test_late_receiver_bookkeeping_cannot_erase_a_durable_writer_hold():
    engine, store = make_store()
    failure = BatchFailure("a" * 12, 1, 12, 12, "data", None, "hashtags")
    store.record_batch_failure(failure)
    store.record_unsequenced_invalid("invalid_json")
    store.record_info("other", "ignored source detail")
    store.record_processing_error("OperationalError")
    assert parse_failure(store.load_state()["last_error"]) == failure
    assert store.load_state()["last_seq"] is None
    engine.dispose()


def test_fresh_socket_is_processing_until_a_recent_commit_and_stale_rate_is_hidden():
    engine, store = make_store()
    store.mark_connected()
    assert store.status_snapshot(60)["health"] == "processing"
    store.persist_batch([event(12)], 50)
    assert store.status_snapshot(60)["health"] == "connected"
    with engine.begin() as connection:
        connection.execute(
            update(IngestionState).values(heartbeat_at=datetime.now(UTC) - timedelta(hours=1))
        )
    status = store.status_snapshot(60)
    assert status["health"] == "stopped" and status["status"] == "interrupted"
    assert status["posts_per_minute"] is None
    assert store.stats_snapshot()["posts_per_minute"] is None
    engine.dispose()
