"""Add durable Bluesky post ingestion, operational state, and coverage tracking."""

import sqlalchemy as sa
from alembic import op

revision = "0002_ingestion"
down_revision = "0001_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("uri", sa.String(512), primary_key=True),
        sa.Column("did", sa.String(256), nullable=False),
        sa.Column("rkey", sa.String(128), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_seq", sa.BigInteger(), nullable=False),
        sa.Column("languages", sa.JSON()),
        sa.UniqueConstraint("event_seq", name="uq_posts_event_seq"),
    )
    op.create_index("ix_posts_did", "posts", ["did"])
    op.create_index("ix_posts_ingested_at", "posts", ["ingested_at"])
    op.create_table(
        "hashtags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tag", sa.String(128), nullable=False, unique=True),
    )
    op.create_table(
        "post_hashtags",
        sa.Column(
            "post_uri",
            sa.String(512),
            sa.ForeignKey("posts.uri", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "hashtag_id",
            sa.Integer(),
            sa.ForeignKey("hashtags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "ingestion_state",
        sa.Column(
            "source_id",
            sa.String(32),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_seq", sa.BigInteger()),
        sa.Column("collection_started_at", sa.DateTime(timezone=True)),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("last_event_at", sa.DateTime(timezone=True)),
        sa.Column("last_persisted_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("posts_per_minute", sa.Float()),
        sa.Column("cursor_expired", sa.Boolean(), nullable=False),
        sa.Column("last_error", sa.String(160)),
        sa.Column("total_events_received", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("valid_post_events", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("posts_persisted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duplicate_events", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("invalid_events", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("processing_errors", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reconnection_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('not_started','connecting','collecting',"
            "'reconnecting','interrupted','error')",
            name="ck_ingestion_state_status",
        ),
    )
    op.create_table(
        "collection_coverage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(32),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("start_seq", sa.BigInteger()),
        sa.Column("end_seq", sa.BigInteger()),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(160)),
    )
    op.create_index("ix_collection_coverage_started_at", "collection_coverage", ["started_at"])
    op.create_table(
        "collection_gaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(32),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gap_start_at", sa.DateTime(timezone=True)),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resume_after_seq", sa.BigInteger()),
        sa.Column("resolution_seq", sa.BigInteger()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(160), nullable=False),
        sa.Column("resolution_note", sa.String(240)),
    )
    op.create_index("ix_collection_gaps_detected_at", "collection_gaps", ["detected_at"])
    op.bulk_insert(
        sa.table(
            "ingestion_state",
            sa.column("source_id", sa.String),
            sa.column("status", sa.String),
            sa.column("cursor_expired", sa.Boolean),
        ),
        [{"source_id": "bluesky", "status": "not_started", "cursor_expired": False}],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_gaps_detected_at", table_name="collection_gaps")
    op.drop_table("collection_gaps")
    op.drop_index("ix_collection_coverage_started_at", table_name="collection_coverage")
    op.drop_table("collection_coverage")
    op.drop_table("ingestion_state")
    op.drop_table("post_hashtags")
    op.drop_table("hashtags")
    op.drop_index("ix_posts_ingested_at", table_name="posts")
    op.drop_index("ix_posts_did", table_name="posts")
    op.drop_table("posts")
