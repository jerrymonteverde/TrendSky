from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from trendsky_api.database import Base
from trendsky_api.ingestion.protocol import JetstreamEvent
from trendsky_api.ingestion.store import IngestionStore
from trendsky_api.models import (
    CollectionCoverage,
    CoverageGap,
    DataSource,
    Hashtag,
    IngestionState,
    Post,
)


def make_store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(DataSource.__table__.insert(), {"id": "bluesky", "name": "Bluesky"})
        connection.execute(
            IngestionState.__table__.insert(),
            {"source_id": "bluesky", "status": "not_started", "cursor_expired": False},
        )
    return engine, IngestionStore(engine)


def event(seq, operation="create", text="#TrendSky launch", rkey="record"):
    return JetstreamEvent(
        seq=seq,
        event_at=datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
        kind="commit",
        did="did:plc:abcdefghijklmnopqrstuvwx",
        operation=operation,
        rkey=rkey,
        record={"text": text, "createdAt": "2026-10-24T11:59:00Z", "langs": ["en"]}
        if operation != "delete"
        else None,
    )


def test_batch_insert_is_idempotent_and_checkpointed():
    engine, store = make_store()
    store.mark_connected()
    first = store.persist_batch([event(12)], 2.0)
    replay = store.persist_batch([event(12)], 2.0)
    assert first["posts_written"] == 1
    assert replay["duplicates"] == 1
    state = store.load_state()
    assert state["last_seq"] == 12
    assert state["posts_persisted"] == 1
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Post)).scalar_one() == 1
        assert connection.execute(select(Hashtag.tag)).scalar_one() == "trendsky"
    engine.dispose()


def test_update_and_delete_replace_or_remove_the_public_post():
    engine, store = make_store()
    store.persist_batch([event(12)], None)
    store.persist_batch([event(13, "update", "new text", "record")], None)
    with engine.connect() as connection:
        assert connection.execute(select(Post.text)).scalar_one() == "new text"
    store.persist_batch([event(14, "delete", rkey="record")], None)
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Post)).scalar_one() == 0
    engine.dispose()


def test_disconnect_creates_explicit_coverage_gap():
    engine, store = make_store()
    store.mark_connected()
    store.persist_batch([event(12)], None)
    store.mark_status("reconnecting", "test interruption")
    with engine.connect() as connection:
        period = connection.execute(select(CollectionCoverage.__table__)).mappings().one()
        gap = connection.execute(select(CoverageGap.__table__)).mappings().one()
        assert period["outcome"] == "reconnecting"
        assert period["end_seq"] == 12
        assert gap["resume_after_seq"] == 12
        assert gap["resolved_at"] is None
    engine.dispose()


def test_transaction_failure_does_not_advance_cursor():
    engine, store = make_store()
    with engine.begin() as connection:
        connection.execute(
            Post.__table__.insert(),
            {
                "uri": "at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/other",
                "did": "did:plc:abcdefghijklmnopqrstuvwx",
                "rkey": "other",
                "event_at": datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
                "ingested_at": datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
                "event_seq": 12,
            },
        )
    try:
        store.persist_batch([event(12)], None)
    except Exception:
        pass
    else:
        raise AssertionError("Expected the unique sequence constraint to reject this batch.")
    assert store.load_state()["last_seq"] is None
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Post)).scalar_one() == 1
    engine.dispose()


def test_nul_in_public_text_does_not_poison_a_checkpoint_batch():
    engine, store = make_store()
    result = store.persist_batch([event(12, text="public\x00conversation #sky")], None)
    assert result["posts_written"] == 1
    assert store.load_state()["last_seq"] == 12
    with engine.connect() as connection:
        assert connection.execute(select(Post.text)).scalar_one() == "public\ufffdconversation #sky"
        assert connection.execute(select(Hashtag.tag)).scalar_one() == "sky"
    engine.dispose()
