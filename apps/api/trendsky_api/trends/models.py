from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from trendsky_api.database import Base


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (Index("ix_topics_normalized_kind", "normalized", "kind", unique=True),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    normalized: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(132), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")


class TopicJob(Base):
    """Transactional coalescing work queue; contains no post text and survives deletes."""

    __tablename__ = "topic_jobs"
    __table_args__ = (Index("ix_topic_jobs_touched", "touched_at", "post_uri"),)

    post_uri: Mapped[str] = mapped_column(String(512), primary_key=True)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    touched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PostTopic(Base):
    __tablename__ = "post_topics"
    __table_args__ = (
        Index("ix_post_topics_activity_language", "activity_at", "language", "topic_id"),
        Index("ix_post_topics_topic_activity", "topic_id", "activity_at"),
    )

    post_uri: Mapped[str] = mapped_column(
        String(512), ForeignKey("posts.uri", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"
    __table_args__ = (
        Index("ix_trends_popular", "window_minutes", "language", "popular_score", "topic_id"),
        Index("ix_trends_rising", "window_minutes", "language", "rising_score", "topic_id"),
        Index("ix_trends_emerging", "window_minutes", "language", "emerging_score", "topic_id"),
    )

    topic_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    window_minutes: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String(8), primary_key=True)
    topic_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_posts: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_contributors: Mapped[int] = mapped_column(Integer, nullable=False)
    popular_score: Mapped[float] = mapped_column(Float, nullable=False)
    rising_score: Mapped[float | None] = mapped_column(Float)
    emerging_score: Mapped[float | None] = mapped_column(Float)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class TrendState(Base):
    __tablename__ = "trend_state"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posts_processed: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    errors: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    backlog: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    processing_ms: Mapped[float | None] = mapped_column(Float)
    query_ms: Mapped[float | None] = mapped_column(Float)
    ranking_ms: Mapped[float | None] = mapped_column(Float)
    coverage_warnings: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    topics_discovered: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
