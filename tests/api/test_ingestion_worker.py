import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from sqlalchemy import create_engine
from trendsky_api.database import Base
from trendsky_api.ingestion.store import IngestionStore
from trendsky_api.ingestion.worker import RateWindow, _connection_session
from trendsky_api.models import DataSource, IngestionState


def test_connection_session_drains_batch_and_commits_checkpoint(tmp_path, monkeypatch):
    async def inline_thread_call(function, *args, **kwargs):
        # The sandbox denies worker-thread scheduling; SQLite remains deterministic here.
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", inline_thread_call)
    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(DataSource.__table__.insert(), {"id": "bluesky", "name": "Bluesky"})
        connection.execute(
            IngestionState.__table__.insert(),
            {"source_id": "bluesky", "status": "not_started", "cursor_expired": False},
        )
    event_frame = (
        b'{"$type":"message","payload":{"$type":"network.bsky.jetstream.'
        b'subscribeEvents#commit","seq":22,"time":"2026-10-24T12:00:00Z",'
        b'"did":"did:plc:abcdefghijklmnopqrstuvwx","operation":"create",'
        b'"collection":"app.bsky.feed.post","rkey":"test",'
        b'"record":{"text":"hello #sky"}}}'
    )

    class FakeSocket:
        subprotocol = "xrpc.v1.json"

        def __aiter__(self):
            async def messages():
                yield event_frame

            return messages()

        async def close(self, **kwargs):
            return None

    @asynccontextmanager
    async def fake_connect(url, **kwargs):
        assert "/xrpc/network.bsky.jetstream.subscribeEvents" in url
        assert kwargs["subprotocols"] == ["xrpc.v1.json"]
        yield FakeSocket()

    async def run():
        session = asyncio.create_task(
            _connection_session(
                IngestionStore(engine),
                SimpleNamespace(
                    jetstream_url="wss://example.test",
                    ingestion_queue_max_size=10,
                    ingestion_batch_size=5,
                    ingestion_flush_interval_ms=100,
                    ingestion_heartbeat_interval_seconds=5,
                ),
                asyncio.Event(),
                RateWindow(),
                fake_connect,
            )
        )
        await asyncio.wait_for(session, timeout=5)

    asyncio.run(run())
    assert IngestionStore(engine).load_state()["last_seq"] == 22
    engine.dispose()
