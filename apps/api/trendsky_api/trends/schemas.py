from datetime import datetime
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel


class Window(IntEnum):
    FIVE = 5
    FIFTEEN = 15
    HOUR = 60
    SIX_HOURS = 360
    DAY = 1440


Language = Literal["all", "en", "es", "unknown", "other"]
Category = Literal["popular", "rising", "emerging"]


class ActivityPoint(BaseModel):
    start: datetime
    end: datetime
    posts: int | None
    observed_posts: int
    coverage_status: str
    coverage_fraction: float


class TrendItem(BaseModel):
    topic_id: str
    label: str
    topic_type: str
    rank: int = 0
    window_minutes: int
    language: str
    current_activity: int
    previous_activity: int | None
    unique_contributors: int
    contributor_capped_activity: int
    growth_percent: float | None
    growth_state: str
    velocity: float | None
    acceleration: float | None
    momentum_score: float
    trend_status: str
    coverage_status: str
    coverage_fraction: float
    previous_coverage_fraction: float
    observed_minutes: float
    comparison_valid: bool
    baseline_windows: int
    baseline_median: float | None
    baseline_mad: float | None
    baseline_deviation: float | None
    baseline_lift: float | None
    baseline_state: str
    popular_score: float
    rising_score: float | None
    emerging_score: float | None
    as_of: datetime
    calculated_at: datetime
    history: list[ActivityPoint]


class TrendPage(BaseModel):
    items: list[TrendItem]
    category: str
    window_minutes: int
    language: str
    limit: int
    offset: int
    has_more: bool
    status: str
    message: str
    last_calculated_at: datetime | None


class TrendEngineStatus(BaseModel):
    status: str
    heartbeat_at: datetime | None
    last_processed_at: datetime | None
    last_calculated_at: datetime | None
    posts_processed: int
    topics_discovered: int
    backlog: int
    errors: int
    processing_ms: float | None
    query_ms: float | None
    ranking_ms: float | None
    coverage_warnings: int
    candidate_limit_per_window: int
    algorithm_version: str = "deterministic-v1"
    health: str = "stopped"
    worker_fresh: bool = False


class TopicMetadata(BaseModel):
    topic_id: str
    label: str
    topic_type: str


class TopicSearchPage(BaseModel):
    items: list[TopicMetadata]
    limit: int
    offset: int
    has_more: bool


class TopicDetail(TopicMetadata):
    status: str
    activity: TrendItem | None
