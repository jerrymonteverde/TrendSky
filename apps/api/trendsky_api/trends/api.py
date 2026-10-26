"""Read-only serving of persisted snapshots; no extraction/aggregation in requests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import Engine, select

from trendsky_api.config import Settings
from trendsky_api.trends.coverage import utc
from trendsky_api.trends.extraction import normalize
from trendsky_api.trends.models import PostTopic, Topic, TrendSnapshot, TrendState
from trendsky_api.trends.schemas import (
    Category,
    Language,
    TopicDetail,
    TopicSearchPage,
    TrendEngineStatus,
    TrendItem,
    TrendPage,
    Window,
)


def item_from_row(row: Any, rank: int = 0) -> TrendItem:
    return TrendItem.model_validate(
        {
            **row["metrics"],
            "topic_id": row["topic_id"],
            "label": row["label"],
            "topic_type": row["kind"],
            "rank": rank,
            "window_minutes": row["window_minutes"],
            "language": row["language"],
            "as_of": row["as_of"],
            "calculated_at": row["calculated_at"],
        }
    )


def snapshot_select() -> Any:
    return select(TrendSnapshot.__table__, Topic.label, Topic.kind).join(
        Topic, Topic.id == TrendSnapshot.topic_id
    )


def create_router(engine_provider: Callable[[], Engine], settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["Trending intelligence"])

    @router.get("/trending/status", response_model=TrendEngineStatus)
    def status() -> TrendEngineStatus:
        with engine_provider().connect() as connection:
            row = dict(
                connection.execute(select(TrendState.__table__).where(TrendState.id == "bluesky"))
                .mappings()
                .one()
            )
        now = datetime.now(UTC)
        fresh = (
            row["heartbeat_at"] is not None
            and 0
            <= (now - utc(row["heartbeat_at"])).total_seconds()
            <= settings.trends_stale_seconds
        )
        if row["status"] not in {"not_started", "disabled", "stopped"} and (
            row["heartbeat_at"] is None
            or now - utc(row["heartbeat_at"]) > timedelta(seconds=settings.trends_stale_seconds)
            or (
                row["status"] == "ready"
                and row["last_calculated_at"] is not None
                and now - utc(row["last_calculated_at"])
                > timedelta(seconds=settings.trends_stale_seconds)
            )
        ):
            row["status"] = "stale"
        if row["status"] in {"not_started", "disabled", "stopped"}:
            health = "stopped"
        elif row["status"] == "stale":
            health = "delayed"
        elif row["status"] == "error":
            health = "error"
        elif row["backlog"] or row["status"] == "catching_up":
            health = "processing_backlog"
        else:
            health = "up_to_date" if row["last_calculated_at"] else "running"
        return TrendEngineStatus.model_validate(
            {
                **row,
                "candidate_limit_per_window": settings.trends_max_topics,
                "health": health,
                "worker_fresh": fresh,
            }
        )

    def ranked(
        category: Category,
        window: Window,
        language: Language,
        limit: int,
        offset: int,
        min_activity: int,
    ) -> TrendPage:
        now = datetime.now(UTC)
        score = getattr(TrendSnapshot, f"{category}_score")
        query = (
            snapshot_select()
            .where(
                TrendSnapshot.window_minutes == window,
                TrendSnapshot.language == language,
                TrendSnapshot.calculated_at
                >= now - timedelta(seconds=settings.trends_stale_seconds),
                TrendSnapshot.current_posts >= max(min_activity, settings.trends_min_posts),
                TrendSnapshot.unique_contributors >= settings.trends_min_contributors,
                score > 0,
            )
            .order_by(
                score.desc(),
                TrendSnapshot.current_posts.desc(),
                TrendSnapshot.unique_contributors.desc(),
                Topic.id,
            )
            .offset(offset)
            .limit(limit + 1)
        )
        with engine_provider().connect() as connection:
            rows = connection.execute(query).mappings().all()
        engine_status = status()
        if engine_status.health in {"stopped", "delayed", "error"}:
            rows = []
        message = (
            "Observed public Bluesky activity. "
            "Coverage and comparison quality are reported per topic."
        )
        state = "ready"
        if not rows:
            state = (
                engine_status.status
                if engine_status.status
                in {"stale", "error", "disabled", "stopped", "catching_up", "not_started"}
                else "collecting_history"
            )
            message = (
                "Not enough historical observations to calculate growth."
                if category != "popular"
                else "Collecting more conversation data."
            )
            if state in {"stale", "error"}:
                message = "Trending results are temporarily unavailable."
            elif state in {"stopped", "disabled", "not_started"}:
                message = "Trend processing is stopped. Ingestion status is reported separately."
        return TrendPage(
            items=[item_from_row(row, offset + i + 1) for i, row in enumerate(rows[:limit])],
            category=category,
            window_minutes=window,
            language=language,
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
            status=state,
            message=message,
            last_calculated_at=engine_status.last_calculated_at,
        )

    @router.get("/trending", response_model=TrendPage)
    def trending(
        category: Category = "popular",
        window: Window = Window.FIVE,
        language: Language = "all",
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
        min_activity: Annotated[int, Query(ge=0, le=100000)] = 0,
    ) -> TrendPage:
        return ranked(category, window, language, limit, offset, min_activity)

    # Explicit category routes share the same validated contract and query implementation.
    @router.get("/trending/{category}", response_model=TrendPage)
    def category_trends(
        category: Category,
        window: Window = Window.FIVE,
        language: Language = "all",
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
        min_activity: Annotated[int, Query(ge=0, le=100000)] = 0,
    ) -> TrendPage:
        return ranked(category, window, language, limit, offset, min_activity)

    @router.get("/topics/search", response_model=TopicSearchPage)
    def search(
        q: Annotated[str, Query(min_length=1, max_length=120)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    ) -> TopicSearchPage:
        value = normalize(q)
        query = select(
            Topic.id.label("topic_id"), Topic.label, Topic.kind.label("topic_type")
        ).where(
            Topic.normalized.startswith(value.lstrip("#"), autoescape=True),
            select(PostTopic.topic_id).where(PostTopic.topic_id == Topic.id).exists(),
        )
        if value.startswith("#"):
            query = query.where(Topic.kind == "hashtag")
        with engine_provider().connect() as connection:
            rows = (
                connection.execute(
                    query.order_by(Topic.normalized, Topic.kind, Topic.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
                .mappings()
                .all()
            )
        return TopicSearchPage.model_validate(
            {
                "items": [dict(row) for row in rows[:limit]],
                "limit": limit,
                "offset": offset,
                "has_more": len(rows) > limit,
            }
        )

    @router.get("/topics/{topic_id}", response_model=TopicDetail)
    @router.get("/topics/{topic_id}/activity", response_model=TopicDetail)
    def detail(
        topic_id: Annotated[str, Path(pattern="^[0-9a-f]{64}$")],
        window: Window = Window.FIVE,
        language: Language = "all",
    ) -> TopicDetail:
        with engine_provider().connect() as connection:
            metadata = (
                connection.execute(
                    select(Topic.__table__).where(
                        Topic.id == topic_id,
                        select(PostTopic.topic_id).where(PostTopic.topic_id == Topic.id).exists(),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if metadata is None:
                raise HTTPException(
                    status_code=404, detail="Topic not found in retained observations."
                )
            row = (
                connection.execute(
                    snapshot_select().where(
                        Topic.id == topic_id,
                        TrendSnapshot.window_minutes == window,
                        TrendSnapshot.language == language,
                    )
                )
                .mappings()
                .one_or_none()
            )
        activity = item_from_row(row) if row is not None else None
        quality = "insufficient_history"
        if activity is not None:
            quality = activity.coverage_status
            if datetime.now(UTC) - utc(activity.calculated_at) > timedelta(
                seconds=settings.trends_stale_seconds
            ):
                quality = "stale_calculation"
                activity.coverage_status = quality
                activity.growth_percent = None
                activity.comparison_valid = False
                activity.trend_status = "Insufficient Data"
        return TopicDetail(
            topic_id=topic_id,
            label=metadata["label"],
            topic_type=metadata["kind"],
            status=quality,
            activity=activity,
        )

    return router
