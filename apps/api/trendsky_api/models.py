from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
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
