from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["connected", "unavailable"]
    schema_status: Literal["ready", "unavailable"]
    version: str = "0.1.0"


class CollectionSummary(BaseModel):
    source: str = "Bluesky"
    collection_status: Literal["not_started"] = "not_started"
    collection_started_at: None = None
    latest_event_at: None = None
    observed_posts: None = None
    message: str = "Collection has not started. No conversation data is available."
