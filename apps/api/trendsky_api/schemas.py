from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["connected", "unavailable"]
    schema_status: Literal["ready", "unavailable"]
    database_health: Literal["available", "unavailable", "degraded"] = "unavailable"
    version: str = "0.1.0"


class CollectionSummary(BaseModel):
    source: str = "Bluesky"
    collection_status: Literal[
        "not_started", "connecting", "collecting", "reconnecting", "interrupted", "error"
    ] = "not_started"
    collection_started_at: datetime | None = None
    latest_event_at: datetime | None = None
    observed_posts: int | None = None
    message: str = "Collection has not started. No conversation data is available."


class IngestionStatus(BaseModel):
    status: Literal[
        "not_started", "connecting", "collecting", "reconnecting", "interrupted", "error"
    ]
    source: str = "bluesky"
    posts_stored: int
    posts_per_minute: float | None
    last_event_at: datetime | None
    last_persisted_at: datetime | None
    last_status_update_at: datetime | None
    collection_started_at: datetime | None
    last_seq: int | None
    cursor_expired: bool
    health: str = "stopped"
    worker_fresh: bool = False
    persistence_fault: dict[str, str | int | bool | None] | None = None
    persistence_lag_seconds: float | None = None
    event_lag_seconds: float | None = None


class IngestionStats(BaseModel):
    posts_stored: int
    total_events_received: int
    valid_post_events: int
    posts_persisted: int
    duplicate_events: int
    invalid_events: int
    processing_errors: int
    reconnection_count: int
    posts_per_minute: float | None


class CoveragePeriod(BaseModel):
    started_at: datetime
    ended_at: datetime | None
    start_seq: int | None
    end_seq: int | None
    outcome: str
    reason: str | None


class CoverageGapEntry(BaseModel):
    gap_start_at: datetime | None
    detected_at: datetime
    resume_after_seq: int | None
    resolution_seq: int | None
    resolved_at: datetime | None
    reason: str
    resolution_note: str | None


class CoverageSnapshot(BaseModel):
    periods: list[CoveragePeriod]
    gaps: list[CoverageGapEntry]
