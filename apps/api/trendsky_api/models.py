from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from trendsky_api.database import Base


class DataSource(Base):
    """Source registry. A row is configuration, never evidence of collection."""

    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint(
            "collection_status IN ('not_started', 'collecting', 'paused')",
            name="ck_data_sources_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    collection_status: Mapped[str] = mapped_column(String(20), default="not_started")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Post(Base):
    """Minimum public post record retained for TrendSky analysis."""

    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_did", "did"),
        Index("ix_posts_ingested_at", "ingested_at"),
        UniqueConstraint("event_seq", name="uq_posts_event_seq"),
    )

    uri: Mapped[str] = mapped_column(String(512), primary_key=True)
    did: Mapped[str] = mapped_column(String(256), nullable=False)
    rkey: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    languages: Mapped[list[str] | None] = mapped_column(JSON)


class Hashtag(Base):
    __tablename__ = "hashtags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)


class PostHashtag(Base):
    __tablename__ = "post_hashtags"

    post_uri: Mapped[str] = mapped_column(
        String(512), ForeignKey("posts.uri", ondelete="CASCADE"), primary_key=True
    )
    hashtag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True
    )


class IngestionState(Base):
    """Durable operational state and cumulative counters for one source worker."""

    __tablename__ = "ingestion_state"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started','connecting','collecting',"
            "'reconnecting','interrupted','error')",
            name="ck_ingestion_state_status",
        ),
    )

    source_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    last_seq: Mapped[int | None] = mapped_column(BigInteger)
    collection_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_persisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posts_per_minute: Mapped[float | None] = mapped_column(Float)
    cursor_expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_error: Mapped[str | None] = mapped_column(String(160))
    total_events_received: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    valid_post_events: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    posts_persisted: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    duplicate_events: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    invalid_events: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    processing_errors: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    reconnection_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")


class CollectionCoverage(Base):
    """One confirmed Jetstream connection period; periods alone do not imply continuity."""

    __tablename__ = "collection_coverage"
    __table_args__ = (Index("ix_collection_coverage_started_at", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_seq: Mapped[int | None] = mapped_column(BigInteger)
    end_seq: Mapped[int | None] = mapped_column(BigInteger)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False, default="collecting")
    reason: Mapped[str | None] = mapped_column(String(160))


class CoverageGap(Base):
    """Known incomplete observation interval; never treated as zero activity."""

    __tablename__ = "collection_gaps"
    __table_args__ = (Index("ix_collection_gaps_detected_at", "detected_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    gap_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resume_after_seq: Mapped[int | None] = mapped_column(BigInteger)
    resolution_seq: Mapped[int | None] = mapped_column(BigInteger)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(String(240))
