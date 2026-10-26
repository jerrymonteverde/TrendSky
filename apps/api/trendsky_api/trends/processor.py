"""Incremental extraction and bounded background SQL aggregation. No HTTP work here."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    BigInteger,
    Connection,
    Engine,
    Integer,
    and_,
    case,
    cast,
    delete,
    func,
    literal,
    or_,
    select,
    text,
    tuple_,
    union_all,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from trendsky_api.config import Settings
from trendsky_api.models import (
    CollectionCoverage,
    CoverageGap,
    Hashtag,
    IngestionState,
    Post,
    PostHashtag,
)
from trendsky_api.trends.coverage import utc, window_coverage
from trendsky_api.trends.extraction import extract_topics
from trendsky_api.trends.models import PostTopic, Topic, TopicJob, TrendSnapshot, TrendState
from trendsky_api.trends.statistics import Activity, calculate

WINDOWS = (5, 15, 60, 360, 1440)
ADVISORY_LOCK = 72648103


def insert_for(connection: Connection, model: Any) -> Any:
    return pg_insert(model) if connection.dialect.name == "postgresql" else sqlite_insert(model)


def chunks(values: list[Any], size: int = 250) -> Any:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def configure_transaction(connection: Connection) -> bool:
    if connection.dialect.name != "postgresql":
        return True
    connection.execute(text("SET LOCAL lock_timeout = '100ms'"))
    connection.execute(text("SET LOCAL statement_timeout = '10000ms'"))
    return bool(
        connection.execute(select(func.pg_try_advisory_xact_lock(ADVISORY_LOCK))).scalar_one()
    )


def process_batch(engine: Engine, settings: Settings, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    started = time.perf_counter()
    with engine.begin() as connection:
        if not configure_transaction(connection):
            return 0
        candidates = (
            connection.execute(
                select(TopicJob.__table__)
                .order_by(TopicJob.touched_at, TopicJob.post_uri)
                .limit(settings.trends_batch_size)
            )
            .mappings()
            .all()
        )
        if not candidates:
            return 0
        uris = [row["post_uri"] for row in candidates]
        exists = set(connection.execute(select(Post.uri).where(Post.uri.in_(uris))).scalars())
        posts_query = select(Post.__table__).where(Post.uri.in_(uris)).order_by(Post.uri)
        if connection.dialect.name == "postgresql":
            posts_query = posts_query.with_for_update(skip_locked=True)
        posts = {row["uri"]: row for row in connection.execute(posts_query).mappings()}
        claim = select(TopicJob.__table__).where(
            or_(
                *[
                    and_(
                        TopicJob.post_uri == row["post_uri"],
                        TopicJob.generation == row["generation"],
                    )
                    for row in candidates
                    if row["post_uri"] in posts or row["post_uri"] not in exists
                ]
            )
        )
        if connection.dialect.name == "postgresql":
            claim = claim.with_for_update(skip_locked=True)
        if not any(uri in posts or uri not in exists for uri in uris):
            return 0
        jobs = connection.execute(claim).mappings().all()
        if not jobs:
            return 0
        uris = [row["post_uri"] for row in jobs]
        tags: dict[str, list[str]] = defaultdict(list)
        for uri, tag in connection.execute(
            select(PostHashtag.post_uri, Hashtag.tag)
            .join(Hashtag)
            .where(PostHashtag.post_uri.in_(uris))
        ):
            tags[uri].append(tag)
        topic_rows: dict[str, dict[str, Any]] = {}
        mention_rows = []
        prior_mentions = connection.execute(
            select(PostTopic.topic_id, PostTopic.activity_at).where(PostTopic.post_uri.in_(uris))
        ).all()
        affected = {row.topic_id for row in prior_mentions}
        for uri in uris:
            post = posts.get(uri)
            if post is None:
                continue
            language, extracted = extract_topics(
                post["text"],
                post["languages"],
                tags[uri],
                phrases=settings.trends_phrases,
                min_length=settings.trends_min_token_length,
                max_keywords=settings.trends_max_keywords_per_post,
            )
            activity = utc(post["created_at"] or post["event_at"])
            if activity > utc(post["event_at"]) + timedelta(minutes=5):
                activity = utc(post["event_at"])
            for item in extracted:
                topic_rows[item.id] = asdict(item)
                affected.add(item.id)
                mention_rows.append(
                    {
                        "post_uri": uri,
                        "topic_id": item.id,
                        "activity_at": activity,
                        "language": language,
                    }
                )
        # Do not wait on a topic currently being invalidated by ingestion.
        existing = set(connection.execute(select(Topic.id).where(Topic.id.in_(affected))).scalars())
        locked_query = select(Topic.id).where(Topic.id.in_(existing))
        if connection.dialect.name == "postgresql":
            locked_query = locked_query.with_for_update(skip_locked=True)
        locked = set(connection.execute(locked_query).scalars())
        if existing != locked:
            return 0
        # New posts after a snapshot's event-time boundary must not erase that valid snapshot.
        earliest: dict[str, datetime] = {}
        for identifier, activity_at in prior_mentions:
            earliest[identifier] = min(earliest.get(identifier, utc(activity_at)), utc(activity_at))
        for mention in mention_rows:
            identifier, activity_at = mention["topic_id"], utc(mention["activity_at"])
            earliest[identifier] = min(earliest.get(identifier, activity_at), activity_at)
        for batch in chunks(list(earliest.items())):
            connection.execute(
                delete(TrendSnapshot).where(
                    or_(
                        *[
                            and_(
                                TrendSnapshot.topic_id == identifier,
                                TrendSnapshot.as_of > activity_at,
                            )
                            for identifier, activity_at in batch
                        ]
                    )
                )
            )
        connection.execute(delete(PostTopic).where(PostTopic.post_uri.in_(uris)))
        connection.execute(
            update(Topic).where(Topic.id.in_(affected)).values(revision=Topic.revision + 1)
        )
        for batch in chunks(list(topic_rows.values())):
            connection.execute(insert_for(connection, Topic).values(batch).on_conflict_do_nothing())
        for batch in chunks(mention_rows):
            connection.execute(
                insert_for(connection, PostTopic).values(batch).on_conflict_do_nothing()
            )
        connection.execute(
            delete(Topic).where(
                Topic.id.in_(affected),
                ~select(PostTopic.topic_id).where(PostTopic.topic_id == Topic.id).exists(),
            )
        )
        connection.execute(delete(TopicJob).where(TopicJob.post_uri.in_(uris)))
        backlog = connection.execute(select(func.count()).select_from(TopicJob)).scalar_one()
        connection.execute(
            update(TrendState)
            .where(TrendState.id == "bluesky")
            .values(
                status="catching_up" if backlog else "ready",
                heartbeat_at=now,
                last_processed_at=now,
                posts_processed=TrendState.posts_processed + len(jobs),
                backlog=backlog,
                processing_ms=(time.perf_counter() - started) * 1000,
            )
        )
    return len(jobs)


def candidate_topics(end: datetime, window: int, settings: Settings) -> Any:
    pt = PostTopic
    return (
        select(pt.topic_id)
        .join(Post, Post.uri == pt.post_uri)
        .where(pt.activity_at >= end - timedelta(minutes=window * 2), pt.activity_at < end)
        .group_by(pt.topic_id)
        .having(
            func.count() >= settings.trends_min_posts,
            func.count(func.distinct(Post.did)) >= settings.trends_min_contributors,
        )
        .order_by(func.count(func.distinct(Post.did)).desc(), func.count().desc(), pt.topic_id)
        .limit(settings.trends_max_topics)
    )


def aggregate_query(
    connection: Connection, start: datetime, end: datetime, window: int, settings: Settings
) -> Any:
    """One scan with grouping sets on PG; equivalent union on portable test DBs."""
    pt = PostTopic
    candidate = candidate_topics(end, window, settings)
    epoch = (
        func.extract("epoch", pt.activity_at)
        if connection.dialect.name == "postgresql"
        else cast(func.strftime("%s", pt.activity_at), BigInteger)
    )
    slot = cast(func.floor((epoch - int(start.timestamp())) / (window * 60)), Integer)
    source = (
        select(pt.topic_id, slot.label("slot"), pt.language, Post.did)
        .join(Post, Post.uri == pt.post_uri)
        .where(pt.activity_at >= start, pt.activity_at < end, pt.topic_id.in_(candidate))
    )
    if connection.dialect.name == "postgresql":
        author = (
            select(
                pt.topic_id,
                slot.label("slot"),
                func.coalesce(pt.language, "all").label("language"),
                Post.did,
                func.count().label("posts"),
            )
            .join(Post, Post.uri == pt.post_uri)
            .where(pt.activity_at >= start, pt.activity_at < end, pt.topic_id.in_(candidate))
            .group_by(
                func.grouping_sets(
                    tuple_(pt.topic_id, slot, pt.language, Post.did),
                    tuple_(pt.topic_id, slot, Post.did),
                )
            )
            .subquery()
        )
    else:
        raw = source.subquery()
        both = union_all(
            select(raw), select(raw.c.topic_id, raw.c.slot, literal("all"), raw.c.did)
        ).subquery()
        author = (
            select(
                both.c.topic_id,
                both.c.slot,
                both.c.language,
                both.c.did,
                func.count().label("posts"),
            )
            .group_by(both.c.topic_id, both.c.slot, both.c.language, both.c.did)
            .subquery()
        )
    return select(
        author.c.topic_id,
        author.c.slot,
        author.c.language,
        func.sum(author.c.posts).label("posts"),
        func.count().label("contributors"),
        func.sum(case((author.c.posts > 3, 3), else_=author.c.posts)).label("capped"),
    ).group_by(author.c.topic_id, author.c.slot, author.c.language)


def coverage_inputs(
    connection: Connection, start: datetime, end: datetime, settings: Settings, now: datetime
) -> tuple[Any, Any, Any]:
    state = (
        connection.execute(
            select(IngestionState.__table__).where(IngestionState.source_id == "bluesky")
        )
        .mappings()
        .one()
    )
    raw = (
        connection.execute(
            select(CollectionCoverage.__table__)
            .where(
                CollectionCoverage.started_at < end,
                or_(CollectionCoverage.ended_at.is_(None), CollectionCoverage.ended_at > start),
            )
            .order_by(CollectionCoverage.started_at)
        )
        .mappings()
        .all()
    )
    live_end = min(
        [end]
        + [utc(state[key]) for key in ("heartbeat_at", "last_event_at") if state[key] is not None]
    )
    if state["heartbeat_at"] is None or state["last_event_at"] is None:
        live_end = start
    periods = [
        (utc(row["started_at"]), utc(row["ended_at"]) if row["ended_at"] else live_end)
        for row in raw
    ]
    gaps = []
    for gap in connection.execute(
        select(CoverageGap.__table__).where(
            func.coalesce(CoverageGap.gap_start_at, CoverageGap.detected_at) < end,
            or_(CoverageGap.resolved_at.is_(None), CoverageGap.resolved_at >= start),
        )
    ).mappings():
        left = utc(gap["gap_start_at"] or gap["detected_at"])
        right = utc(gap["resolved_at"] or gap["detected_at"])
        if "replay_required" in gap["reason"] or "cursor_expired" in gap["reason"]:
            right = next((a for a, _ in periods if a >= right), end)
        gaps.append((left, right))
    first = state["collection_started_at"]
    history_start = (
        max(utc(first), now - timedelta(days=settings.ingestion_retention_days)) if first else None
    )
    return periods, gaps, history_start


def pending_history(connection: Connection, asof: datetime) -> int:
    return int(
        connection.execute(
            select(func.count())
            .select_from(TopicJob)
            .outerjoin(Post, Post.uri == TopicJob.post_uri)
            .where(or_(TopicJob.touched_at <= asof, Post.created_at < asof, Post.event_at < asof))
        ).scalar_one()
    )


def refresh_window(
    engine: Engine, settings: Settings, window: int, asof: datetime, now: datetime
) -> dict[str, float | int]:
    count_slots = settings.trends_baseline_windows + 2
    start = asof - timedelta(minutes=window * count_slots)
    started = time.perf_counter()
    with engine.begin() as connection:
        if not configure_transaction(connection):
            return {"published": 0}
        # Capture revision BEFORE aggregate reads. Final publication locks and rechecks it.
        revisions = dict(
            connection.execute(
                select(Topic.id, Topic.revision).where(
                    Topic.id.in_(candidate_topics(asof, window, settings))
                )
            ).all()
        )
        periods, gaps, first = coverage_inputs(connection, start, asof, settings, now)
        qualities = [
            window_coverage(
                asof - timedelta(minutes=window * (i + 1)),
                asof - timedelta(minutes=window * i),
                periods,
                gaps,
                first,
            )
            for i in range(count_slots)
        ]
        query_start = time.perf_counter()
        rows = (
            connection.execute(aggregate_query(connection, start, asof, window, settings))
            .mappings()
            .all()
        )
        query_ms = (time.perf_counter() - query_start) * 1000
        by_topic: dict[tuple[str, str], dict[int, Activity]] = defaultdict(dict)
        for row in rows:
            reverse_slot = count_slots - 1 - row["slot"]
            if 0 <= reverse_slot < count_slots:
                by_topic[(row["topic_id"], row["language"])][reverse_slot] = Activity(
                    int(row["posts"]), row["contributors"], int(row["capped"])
                )
        rank_start = time.perf_counter()
        snapshots = []
        for (identifier, language), values in sorted(by_topic.items()):
            current, previous = values.get(0, Activity()), values.get(1, Activity())
            if not current.posts and not previous.posts:
                continue
            metrics = calculate(
                current,
                previous,
                [values.get(i, Activity()) for i in range(2, count_slots)],
                qualities,
                window,
                settings,
            )
            metrics["history"] = [
                {
                    "start": (asof - timedelta(minutes=window * (i + 1))).isoformat(),
                    "end": (asof - timedelta(minutes=window * i)).isoformat(),
                    "posts": values.get(i, Activity()).posts if qualities[i].complete else None,
                    "observed_posts": values.get(i, Activity()).posts,
                    "coverage_status": qualities[i].quality,
                    "coverage_fraction": qualities[i].fraction,
                }
                for i in reversed(range(count_slots))
            ]
            snapshots.append(
                {
                    "topic_id": identifier,
                    "window_minutes": window,
                    "language": language,
                    "topic_revision": revisions.get(identifier, -1),
                    "current_posts": current.posts,
                    "unique_contributors": current.contributors,
                    "popular_score": metrics["popular_score"],
                    "rising_score": metrics["rising_score"],
                    "emerging_score": metrics["emerging_score"],
                    "as_of": asof,
                    "calculated_at": now,
                    "metrics": metrics,
                }
            )
        ids = {row["topic_id"] for row in snapshots}
        final_query = select(Topic.id, Topic.revision).where(Topic.id.in_(ids)).order_by(Topic.id)
        if connection.dialect.name == "postgresql":
            final_query = final_query.with_for_update(skip_locked=True)
        final_revisions = dict(connection.execute(final_query).all())
        snapshots = [
            row
            for row in snapshots
            if final_revisions.get(row["topic_id"]) == row["topic_revision"]
        ]
        if pending_history(connection, asof):
            return {"published": 0, "query_ms": query_ms}
        connection.execute(delete(TrendSnapshot).where(TrendSnapshot.window_minutes == window))
        for batch in chunks(snapshots, 100):
            connection.execute(insert_for(connection, TrendSnapshot).values(batch))
        connection.execute(
            update(TrendState)
            .where(TrendState.id == "bluesky")
            .values(
                status="ready",
                heartbeat_at=now,
                last_calculated_at=now,
                query_ms=query_ms,
                ranking_ms=(time.perf_counter() - rank_start) * 1000,
                coverage_warnings=sum(not q.complete for q in qualities),
            )
        )
    return {
        "published": len(snapshots),
        "query_ms": query_ms,
        "duration_ms": (time.perf_counter() - started) * 1000,
    }


def refresh(
    engine: Engine, settings: Settings, now: datetime | None = None
) -> list[dict[str, float | int]]:
    now = utc(now or datetime.now(UTC))
    asof = (now - timedelta(seconds=settings.trends_lateness_seconds)).replace(
        second=0, microsecond=0
    )
    with engine.begin() as connection:
        # Old pending changes mean the point-in-time extraction is not ready to publish.
        old_jobs = pending_history(connection, asof)
        topic_count = connection.execute(select(func.count()).select_from(Topic)).scalar_one()
        connection.execute(
            update(TrendState)
            .where(TrendState.id == "bluesky")
            .values(topics_discovered=topic_count)
        )
        if old_jobs:
            connection.execute(
                update(TrendState)
                .where(TrendState.id == "bluesky")
                .values(status="catching_up", backlog=old_jobs, heartbeat_at=now)
            )
            return []
    return [refresh_window(engine, settings, window, asof, now) for window in WINDOWS]
