"""Transactional Postgres/SQLite persistence for posts, checkpoints, metrics, and coverage."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import Engine, and_, delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from trendsky_api.ingestion.failures import BatchFailure, parse_failure
from trendsky_api.ingestion.protocol import JetstreamEvent, hashtags_from_record
from trendsky_api.ingestion.text import RecordValidationError, postgres_text, validate_identifier
from trendsky_api.models import (
    CollectionCoverage,
    CoverageGap,
    Hashtag,
    IngestionState,
    Post,
    PostHashtag,
)

SOURCE_ID = "bluesky"
logger = logging.getLogger("trendsky.ingestion")
PERSISTENCE_PHASE: ContextVar[str] = ContextVar("persistence_phase", default="batch")


@dataclass(frozen=True, slots=True)
class InvalidFrame:
    seq: int | None
    reason: str


IngestItem = JetstreamEvent | InvalidFrame


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def preserve_hold(current: str | None, message: str) -> str:
    """Receiver bookkeeping already in flight must not erase a writer's durable hold."""
    failure = parse_failure(current)
    return current if failure is not None and failure.blocked and current else message


def operational_health(row: Any, now: datetime, timeout: int) -> dict[str, Any]:
    heartbeat = as_utc(row.heartbeat_at)
    persisted = as_utc(row.last_persisted_at)
    event = as_utc(row.last_event_at)
    fresh = heartbeat is not None and 0 <= (now - heartbeat).total_seconds() <= timeout
    failure = parse_failure(row.last_error)
    status = row.status
    if status in {"connecting", "collecting", "reconnecting"} and not fresh:
        status = "interrupted"
    if failure is not None and failure.blocked:
        status = "error"
    health = "stopped"
    if row.cursor_expired:
        health = "cursor_expired"
    elif failure is not None or (row.last_error or "").startswith("Persistence retry exhausted"):
        health = "persistence_failure"
    elif status == "error":
        health = "persistence_failure"
    elif fresh and status in {"connecting", "reconnecting"}:
        health = status
    elif fresh and status == "collecting":
        health = (
            "connected"
            if persisted and (now - persisted).total_seconds() <= timeout
            else "processing"
        )
    return {
        "status": status,
        "health": health,
        "worker_fresh": fresh,
        "persistence_fault": asdict(failure) if failure is not None else None,
        "persistence_lag_seconds": max(0, (now - persisted).total_seconds()) if persisted else None,
        "event_lag_seconds": max(0, (now - event).total_seconds()) if event else None,
        "posts_per_minute": row.posts_per_minute if health == "connected" else None,
    }


def _counter_values(row: IngestionState) -> dict[str, int]:
    return {
        "total_events_received": row.total_events_received,
        "valid_post_events": row.valid_post_events,
        "posts_persisted": row.posts_persisted,
        "duplicate_events": row.duplicate_events,
        "invalid_events": row.invalid_events,
        "processing_errors": row.processing_errors,
        "reconnection_count": row.reconnection_count,
    }


class IngestionStore:
    """Small sync SQLAlchemy repository used via asyncio.to_thread by the worker."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _state(self, connection: Any, *, lock: bool = False) -> Any:
        statement = select(IngestionState.__table__).where(IngestionState.source_id == SOURCE_ID)
        if lock and self.engine.dialect.name == "postgresql":
            statement = statement.with_for_update()
        result = connection.execute(statement).mappings().one_or_none()
        row = SimpleNamespace(**result) if result is not None else None
        if row is None:
            raise RuntimeError("Ingestion state is missing; run the database migrations first.")
        return row

    def load_state(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = self._state(connection)
            return {
                "status": row.status,
                "last_seq": row.last_seq,
                "collection_started_at": row.collection_started_at,
                "connected_at": row.connected_at,
                "last_event_at": row.last_event_at,
                "last_persisted_at": row.last_persisted_at,
                "heartbeat_at": row.heartbeat_at,
                "cursor_expired": row.cursor_expired,
                "last_error": row.last_error,
                **_counter_values(row),
            }

    def mark_connecting(self) -> None:
        now = utc_now()
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            active_period = connection.execute(
                select(CollectionCoverage.id)
                .where(
                    CollectionCoverage.source_id == SOURCE_ID,
                    CollectionCoverage.ended_at.is_(None),
                )
                .limit(1)
            ).scalar_one_or_none()
            connection.execute(
                update(CollectionCoverage)
                .where(
                    CollectionCoverage.source_id == SOURCE_ID,
                    CollectionCoverage.ended_at.is_(None),
                )
                .values(ended_at=now, outcome="interrupted", reason="worker_restarted")
            )
            if active_period is not None:
                connection.execute(
                    insert(CoverageGap).values(
                        source_id=SOURCE_ID,
                        gap_start_at=row.last_event_at,
                        detected_at=now,
                        resume_after_seq=row.last_seq,
                        reason="worker_restarted;replay_required",
                    )
                )
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(status="connecting", heartbeat_at=now, connected_at=None, last_error=None)
            )

    def mark_connected(self) -> None:
        now = utc_now()
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    status="collecting",
                    heartbeat_at=now,
                    connected_at=now,
                    collection_started_at=row.collection_started_at or now,
                    posts_per_minute=0.0,
                    last_error=None,
                )
            )
            connection.execute(
                insert(CollectionCoverage).values(
                    source_id=SOURCE_ID,
                    started_at=now,
                    start_seq=row.last_seq,
                    outcome="collecting",
                )
            )

    def mark_status(self, status: str, reason: str | None = None) -> None:
        reason = postgres_text(reason)[:160] if reason is not None else None
        now = utc_now()
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    status=status,
                    heartbeat_at=now,
                    connected_at=None,
                    last_error=reason,
                    reconnection_count=row.reconnection_count
                    + (1 if status == "reconnecting" else 0),
                )
            )
            if status in {"reconnecting", "interrupted", "error", "not_started"}:
                active_period = connection.execute(
                    select(CollectionCoverage.id)
                    .where(
                        CollectionCoverage.source_id == SOURCE_ID,
                        CollectionCoverage.ended_at.is_(None),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                connection.execute(
                    update(CollectionCoverage)
                    .where(
                        CollectionCoverage.source_id == SOURCE_ID,
                        CollectionCoverage.ended_at.is_(None),
                    )
                    .values(ended_at=now, outcome=status, reason=reason)
                )
                if active_period is not None:
                    connection.execute(
                        insert(CoverageGap).values(
                            source_id=SOURCE_ID,
                            gap_start_at=row.last_event_at,
                            detected_at=now,
                            resume_after_seq=row.last_seq,
                            reason=f"{status};replay_required",
                        )
                    )

    def heartbeat(self, posts_per_minute: float | None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(IngestionState)
                .where(
                    IngestionState.source_id == SOURCE_ID,
                    IngestionState.status == "collecting",
                )
                .values(heartbeat_at=utc_now(), posts_per_minute=posts_per_minute)
            )

    def record_unsequenced_invalid(self, reason: str) -> None:
        reason = postgres_text(reason)[:120]
        now = utc_now()
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    total_events_received=row.total_events_received + 1,
                    invalid_events=row.invalid_events + 1,
                    last_error=preserve_hold(row.last_error, f"Malformed frame: {reason}"[:160]),
                )
            )
            connection.execute(
                insert(CoverageGap).values(
                    source_id=SOURCE_ID,
                    gap_start_at=row.last_event_at,
                    detected_at=now,
                    resume_after_seq=row.last_seq,
                    reason=f"unparseable_frame:{reason}"[:160],
                )
            )

    def record_info(self, name: str, message: str) -> None:
        name = postgres_text(name)[:80]
        now = utc_now()
        bounded = f"Jetstream info: {name}"[:160]
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    total_events_received=row.total_events_received + 1,
                    last_error=preserve_hold(row.last_error, bounded),
                )
            )
            if name in {"OutdatedCursor", "CursorTooOld", "FutureCursor"}:
                connection.execute(
                    insert(CoverageGap).values(
                        source_id=SOURCE_ID,
                        gap_start_at=row.last_event_at,
                        detected_at=now,
                        resume_after_seq=row.last_seq,
                        reason=f"jetstream_info:{name}"[:160],
                    )
                )

    def record_cursor_expired(self) -> None:
        now = utc_now()
        reason = "Jetstream replay cursor expired; operator review is required."
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    status="interrupted",
                    heartbeat_at=now,
                    connected_at=None,
                    cursor_expired=True,
                    posts_per_minute=None,
                    last_error=reason,
                )
            )
            connection.execute(
                update(CollectionCoverage)
                .where(
                    CollectionCoverage.source_id == SOURCE_ID,
                    CollectionCoverage.ended_at.is_(None),
                )
                .values(ended_at=now, outcome="cursor_expired", reason=reason)
            )
            connection.execute(
                insert(CoverageGap).values(
                    source_id=SOURCE_ID,
                    gap_start_at=row.last_event_at,
                    detected_at=now,
                    resume_after_seq=row.last_seq,
                    reason="jetstream_cursor_expired; backfill_or_operator_reset_required",
                )
            )

    def record_processing_error(self, category: str) -> None:
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    processing_errors=row.processing_errors + 1,
                    last_error=preserve_hold(
                        row.last_error, f"Persistence retry exhausted: {category}"[:160]
                    ),
                )
            )

    def record_batch_failure(self, failure: BatchFailure) -> None:
        """Durable review marker and gap, never checkpoint advancement or event deletion."""
        now = utc_now()
        marker = failure.encode()
        with self.engine.begin() as connection:
            row = self._state(connection, lock=True)
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    status="error",
                    heartbeat_at=now,
                    connected_at=None,
                    posts_per_minute=None,
                    last_error=marker,
                    processing_errors=row.processing_errors + 1,
                )
            )
            connection.execute(
                update(CollectionCoverage)
                .where(
                    CollectionCoverage.source_id == SOURCE_ID, CollectionCoverage.ended_at.is_(None)
                )
                .values(
                    ended_at=now, outcome="error", reason="persistence_blocked; checkpoint retained"
                )
            )
            connection.execute(
                insert(CoverageGap).values(
                    source_id=SOURCE_ID,
                    gap_start_at=row.last_event_at,
                    detected_at=now,
                    resume_after_seq=row.last_seq,
                    reason=f"persistence_blocked:{failure.batch_id}",
                    resolution_note=(
                        "Operator review required. No event skipped; checkpoint unchanged."
                    ),
                )
            )

    def persist_batch(
        self, items: list[IngestItem], posts_per_minute: float | None
    ) -> dict[str, int]:
        token = PERSISTENCE_PHASE.set("batch")
        try:
            return self._persist_batch(items, posts_per_minute)
        except Exception as exc:
            exc.trendsky_phase = PERSISTENCE_PHASE.get()  # type: ignore[attr-defined]
            raise
        finally:
            PERSISTENCE_PHASE.reset(token)

    def _persist_batch(
        self, items: list[IngestItem], posts_per_minute: float | None
    ) -> dict[str, int]:
        """Fold one ordered batch and commit post changes plus checkpoint atomically."""
        now = utc_now()
        received = len(items)
        normalized_texts = 0
        normalized_metadata = 0
        counts = {"duplicates": 0, "invalid": 0, "post_events": 0, "posts_written": 0}
        with self.engine.begin() as connection:
            PERSISTENCE_PHASE.set("checkpoint_lock")
            state = self._state(connection, lock=True)
            previous_seq = state.last_seq or 0
            max_seq = previous_seq
            seen: set[int] = set()
            accepted: list[JetstreamEvent] = []
            invalid_sequenced: list[InvalidFrame] = []
            unsequenced_invalid = 0
            for item in sorted(
                items, key=lambda value: value.seq if value.seq is not None else 2**63
            ):
                if isinstance(item, InvalidFrame):
                    counts["invalid"] += 1
                    if item.seq is None:
                        unsequenced_invalid += 1
                        continue
                    if item.seq <= previous_seq or item.seq in seen:
                        counts["duplicates"] += 1
                        continue
                    seen.add(item.seq)
                    max_seq = max(max_seq, item.seq)
                    invalid_sequenced.append(item)
                    continue
                if item.seq <= previous_seq or item.seq in seen:
                    counts["duplicates"] += 1
                    continue
                seen.add(item.seq)
                max_seq = max(max_seq, item.seq)
                accepted.append(item)

            pending_posts: dict[str, tuple[JetstreamEvent, set[str]]] = {}
            pending_deletes: dict[str, int] = {}
            did_tombstones: dict[str, int] = {}
            for event in accepted:
                if event.did is None:
                    continue
                PERSISTENCE_PHASE.set("validation")
                validate_identifier(event.did, 256)
                if event.seq > 2**63 - 1:
                    raise RecordValidationError("unsupported_event_sequence")
                if (
                    event.kind == "account"
                    and event.account_active is False
                    and event.account_status == "deleted"
                ):
                    did_tombstones[event.did] = event.seq
                    for uri, (pending, _) in list(pending_posts.items()):
                        if pending.did == event.did and pending.seq <= event.seq:
                            del pending_posts[uri]
                    continue
                if event.kind == "sync":
                    did_tombstones[event.did] = event.seq
                    for uri, (pending, _) in list(pending_posts.items()):
                        if pending.did == event.did and pending.seq <= event.seq:
                            del pending_posts[uri]
                    continue
                if event.kind != "commit" or event.operation is None or event.rkey is None:
                    continue
                validate_identifier(event.rkey, 128)
                counts["post_events"] += 1
                uri = f"at://{event.did}/app.bsky.feed.post/{event.rkey}"
                if event.seq <= did_tombstones.get(event.did, 0):
                    continue
                if event.operation == "delete":
                    pending_posts.pop(uri, None)
                    pending_deletes[uri] = event.seq
                    continue
                record = event.record or {}
                pending_deletes.pop(uri, None)
                pending_posts[uri] = (event, hashtags_from_record(record))

            PERSISTENCE_PHASE.set("coverage")
            for item in invalid_sequenced:
                connection.execute(
                    insert(CoverageGap).values(
                        source_id=SOURCE_ID,
                        gap_start_at=state.last_event_at,
                        detected_at=now,
                        resume_after_seq=previous_seq,
                        resolution_seq=item.seq,
                        reason=postgres_text(f"invalid_event_with_sequence:{item.reason}")[:160],
                        resolution_note=(
                            "Checkpoint advanced after recording the invalid frame; "
                            "analysis must exclude this interval."
                        ),
                    )
                )
            if unsequenced_invalid:
                connection.execute(
                    insert(CoverageGap).values(
                        source_id=SOURCE_ID,
                        gap_start_at=state.last_event_at,
                        detected_at=now,
                        resume_after_seq=previous_seq,
                        reason="unparseable_frame_without_sequence; coverage_uncertain",
                    )
                )

            PERSISTENCE_PHASE.set("deletes")
            if did_tombstones:
                conditions = [
                    and_(Post.did == did, Post.event_seq <= seq)
                    for did, seq in did_tombstones.items()
                ]
                connection.execute(
                    delete(PostHashtag).where(
                        PostHashtag.post_uri.in_(select(Post.uri).where(or_(*conditions)))
                    )
                )
                connection.execute(delete(Post).where(or_(*conditions)))
            if pending_deletes:
                conditions = [
                    and_(Post.uri == uri, Post.event_seq <= seq)
                    for uri, seq in pending_deletes.items()
                ]
                connection.execute(
                    delete(PostHashtag).where(
                        PostHashtag.post_uri.in_(select(Post.uri).where(or_(*conditions)))
                    )
                )
                connection.execute(delete(Post).where(or_(*conditions)))

            post_rows: list[dict[str, Any]] = []
            tags_by_uri: dict[str, set[str]] = {}
            PERSISTENCE_PHASE.set("validation")
            for uri, (event, tags) in pending_posts.items():
                record = event.record or {}
                post_text = record.get("text")
                if isinstance(post_text, str):
                    clean = postgres_text(post_text)
                    normalized_texts += int(clean != post_text)
                    post_text = clean
                clean_tags = {postgres_text(tag) for tag in tags}
                normalized_metadata += sum(postgres_text(tag) != tag for tag in tags)
                if any(len(tag) > 128 for tag in clean_tags):
                    raise RecordValidationError("unsupported_hashtag_length")
                created_at = None
                raw_created = record.get("createdAt")
                if isinstance(raw_created, str):
                    try:
                        created_at = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
                        if created_at.tzinfo is not None:
                            created_at = created_at.astimezone(UTC)
                        else:
                            created_at = None
                    except (ValueError, OverflowError):
                        created_at = None
                raw_langs = record.get("langs")
                languages = (
                    list(
                        dict.fromkeys(
                            postgres_text(lang)
                            for lang in raw_langs
                            if isinstance(lang, str) and len(lang) <= 35
                        )
                    )[:16]
                    if isinstance(raw_langs, list)
                    else None
                )
                if isinstance(raw_langs, list):
                    normalized_metadata += sum(
                        postgres_text(lang) != lang for lang in raw_langs if isinstance(lang, str)
                    )
                post_rows.append(
                    {
                        "uri": uri,
                        "did": event.did,
                        "rkey": event.rkey,
                        "text": post_text if isinstance(post_text, str) else None,
                        "created_at": created_at,
                        "event_at": event.event_at,
                        "ingested_at": now,
                        "event_seq": event.seq,
                        "languages": languages,
                    }
                )
                tags_by_uri[uri] = clean_tags

            if post_rows:
                PERSISTENCE_PHASE.set("posts")
                dialect = self.engine.dialect.name
                if dialect == "postgresql":
                    insert_stmt: Any = pg_insert(Post).values(post_rows)
                elif dialect == "sqlite":
                    insert_stmt = sqlite_insert(Post).values(post_rows)
                else:
                    raise RuntimeError(f"Unsupported ingestion database dialect: {dialect}")
                update_fields = {
                    key: getattr(insert_stmt.excluded, key)
                    for key in (
                        "did",
                        "rkey",
                        "text",
                        "created_at",
                        "event_at",
                        "ingested_at",
                        "event_seq",
                        "languages",
                    )
                }
                connection.execute(
                    insert_stmt.on_conflict_do_update(
                        index_elements=[Post.uri],
                        set_=update_fields,
                        where=insert_stmt.excluded.event_seq > Post.event_seq,
                    )
                )
                all_tags = sorted({tag for values in tags_by_uri.values() for tag in values})
                PERSISTENCE_PHASE.set("hashtags")
                tag_ids: dict[str, int] = {}
                if all_tags:
                    tag_rows = [{"tag": tag} for tag in all_tags]
                    if dialect == "postgresql":
                        connection.execute(
                            pg_insert(Hashtag)
                            .values(tag_rows)
                            .on_conflict_do_nothing(index_elements=[Hashtag.tag])
                        )
                    else:
                        connection.execute(
                            sqlite_insert(Hashtag)
                            .values(tag_rows)
                            .on_conflict_do_nothing(index_elements=[Hashtag.tag])
                        )
                    tag_ids = dict(
                        connection.execute(
                            select(Hashtag.tag, Hashtag.id).where(Hashtag.tag.in_(all_tags))
                        ).all()
                    )
                uris = list(tags_by_uri)
                PERSISTENCE_PHASE.set("hashtag_links")
                connection.execute(delete(PostHashtag).where(PostHashtag.post_uri.in_(uris)))
                links = [
                    {"post_uri": uri, "hashtag_id": tag_ids[tag]}
                    for uri, values in tags_by_uri.items()
                    for tag in values
                    if tag in tag_ids
                ]
                if links:
                    if dialect == "postgresql":
                        connection.execute(
                            pg_insert(PostHashtag).values(links).on_conflict_do_nothing()
                        )
                    else:
                        connection.execute(
                            sqlite_insert(PostHashtag).values(links).on_conflict_do_nothing()
                        )
                counts["posts_written"] = len(post_rows)

            max_event_at = max((item.event_at for item in accepted), default=state.last_event_at)
            PERSISTENCE_PHASE.set("checkpoint")
            connection.execute(
                update(IngestionState)
                .where(IngestionState.source_id == SOURCE_ID)
                .values(
                    last_seq=max_seq if max_seq > previous_seq else state.last_seq,
                    last_event_at=max_event_at,
                    last_persisted_at=now
                    if accepted or invalid_sequenced
                    else state.last_persisted_at,
                    heartbeat_at=now,
                    posts_per_minute=posts_per_minute,
                    total_events_received=state.total_events_received + received,
                    valid_post_events=state.valid_post_events + counts["post_events"],
                    posts_persisted=state.posts_persisted + counts["posts_written"],
                    duplicate_events=state.duplicate_events + counts["duplicates"],
                    invalid_events=state.invalid_events + counts["invalid"],
                    last_error=(
                        "Invalid event received; coverage gap recorded."
                        if counts["invalid"]
                        else state.last_error
                    ),
                )
            )
            PERSISTENCE_PHASE.set("coverage_cursor")
            coverage = connection.execute(
                select(CollectionCoverage.id)
                .where(
                    CollectionCoverage.source_id == SOURCE_ID,
                    CollectionCoverage.ended_at.is_(None),
                )
                .order_by(CollectionCoverage.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if coverage is not None and max_seq > previous_seq:
                connection.execute(
                    update(CollectionCoverage)
                    .where(CollectionCoverage.id == coverage)
                    .values(end_seq=max_seq)
                )
            PERSISTENCE_PHASE.set("commit")
        if normalized_texts:
            logger.warning("post_text_normalized", extra={"normalized_records": normalized_texts})
        if normalized_metadata:
            logger.warning(
                "post_metadata_normalized", extra={"normalized_records": normalized_metadata}
            )
        return counts

    def cleanup_retention(self, retention_days: int, limit: int = 5000) -> int:
        cutoff = utc_now() - timedelta(days=retention_days)
        with self.engine.begin() as connection:
            expired = list(
                connection.execute(
                    select(Post.uri).where(Post.ingested_at < cutoff).limit(limit)
                ).scalars()
            )
            if not expired:
                return 0
            connection.execute(delete(PostHashtag).where(PostHashtag.post_uri.in_(expired)))
            connection.execute(delete(Post).where(Post.uri.in_(expired)))
            connection.execute(
                delete(Hashtag).where(
                    ~select(PostHashtag.hashtag_id)
                    .where(PostHashtag.hashtag_id == Hashtag.id)
                    .exists()
                )
            )
            return len(expired)

    def status_snapshot(self, heartbeat_timeout_seconds: int) -> dict[str, Any]:
        now = utc_now()
        with self.engine.connect() as connection:
            row = self._state(connection)
            health = operational_health(row, now, heartbeat_timeout_seconds)
            post_count = connection.execute(select(func.count()).select_from(Post)).scalar_one()
            return {
                **health,
                "source": "bluesky",
                "posts_stored": post_count,
                "last_event_at": as_utc(row.last_event_at),
                "last_persisted_at": as_utc(row.last_persisted_at),
                "last_status_update_at": as_utc(row.heartbeat_at),
                "collection_started_at": as_utc(row.collection_started_at),
                "last_seq": row.last_seq,
                "cursor_expired": row.cursor_expired,
            }

    def stats_snapshot(self, heartbeat_timeout_seconds: int = 60) -> dict[str, int | float | None]:
        with self.engine.connect() as connection:
            row = self._state(connection)
            posts_stored = connection.execute(select(func.count()).select_from(Post)).scalar_one()
            return {
                "posts_stored": posts_stored,
                **_counter_values(row),
                "posts_per_minute": operational_health(row, utc_now(), heartbeat_timeout_seconds)[
                    "posts_per_minute"
                ],
            }

    def coverage_snapshot(self, limit: int) -> dict[str, list[dict[str, Any]]]:
        with self.engine.connect() as connection:
            periods = (
                connection.execute(
                    select(CollectionCoverage.__table__)
                    .where(CollectionCoverage.source_id == SOURCE_ID)
                    .order_by(CollectionCoverage.started_at.desc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            gaps = (
                connection.execute(
                    select(CoverageGap.__table__)
                    .where(CoverageGap.source_id == SOURCE_ID)
                    .order_by(CoverageGap.detected_at.desc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            return {
                "periods": [
                    {
                        "started_at": p["started_at"],
                        "ended_at": p["ended_at"],
                        "start_seq": p["start_seq"],
                        "end_seq": p["end_seq"],
                        "outcome": p["outcome"],
                        "reason": p["reason"],
                    }
                    for p in periods
                ],
                "gaps": [
                    {
                        "gap_start_at": g["gap_start_at"],
                        "detected_at": g["detected_at"],
                        "resume_after_seq": g["resume_after_seq"],
                        "resolution_seq": g["resolution_seq"],
                        "resolved_at": g["resolved_at"],
                        "reason": g["reason"],
                        "resolution_note": g["resolution_note"],
                    }
                    for g in gaps
                ],
            }
