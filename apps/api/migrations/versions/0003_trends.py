"""Add deterministic trend processing without changing or removing source observations."""

import sqlalchemy as sa
from alembic import op

revision = "0003_trends"
down_revision = "0002_ingestion"
branch_labels = None
depends_on = None

PG_TRIGGER = """
CREATE FUNCTION trendsky_post_changed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE affected text[];
BEGIN
  IF TG_OP <> 'INSERT' THEN
    SELECT array_agg(topic_id) INTO affected FROM post_topics WHERE post_uri = OLD.uri;
    UPDATE topics SET revision = revision + 1 WHERE id = ANY(affected);
    DELETE FROM trend_snapshots s WHERE s.topic_id = ANY(affected)
      AND EXISTS (SELECT 1 FROM post_topics pt WHERE pt.post_uri=OLD.uri
        AND pt.topic_id=s.topic_id AND pt.activity_at < s.as_of);
    DELETE FROM post_topics WHERE post_uri = OLD.uri;
    DELETE FROM topics t WHERE t.id = ANY(affected)
      AND NOT EXISTS (SELECT 1 FROM post_topics pt WHERE pt.topic_id = t.id);
  END IF;
  INSERT INTO topic_jobs(post_uri, generation, touched_at)
    VALUES (CASE WHEN TG_OP = 'DELETE' THEN OLD.uri ELSE NEW.uri END, 1, clock_timestamp())
    ON CONFLICT (post_uri) DO UPDATE
      SET generation = topic_jobs.generation + 1, touched_at = EXCLUDED.touched_at;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$
"""


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '2s'")
        op.execute("SET LOCAL statement_timeout = '30s'")
    op.create_table(
        "topics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("normalized", sa.String(128), nullable=False),
        sa.Column("label", sa.String(132), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
    )
    op.create_index("ix_topics_normalized_kind", "topics", ["normalized", "kind"], unique=True)
    op.create_table(
        "topic_jobs",
        sa.Column("post_uri", sa.String(512), primary_key=True),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("touched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_topic_jobs_touched", "topic_jobs", ["touched_at", "post_uri"])
    op.create_table(
        "post_topics",
        sa.Column(
            "post_uri",
            sa.String(512),
            sa.ForeignKey("posts.uri", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "topic_id",
            sa.String(64),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
    )
    op.create_index(
        "ix_post_topics_activity_language", "post_topics", ["activity_at", "language", "topic_id"]
    )
    op.create_index("ix_post_topics_topic_activity", "post_topics", ["topic_id", "activity_at"])
    op.create_table(
        "trend_snapshots",
        sa.Column(
            "topic_id",
            sa.String(64),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("window_minutes", sa.Integer(), primary_key=True),
        sa.Column("language", sa.String(8), primary_key=True),
        sa.Column("topic_revision", sa.BigInteger(), nullable=False),
        sa.Column("current_posts", sa.Integer(), nullable=False),
        sa.Column("unique_contributors", sa.Integer(), nullable=False),
        sa.Column("popular_score", sa.Float(), nullable=False),
        sa.Column("rising_score", sa.Float()),
        sa.Column("emerging_score", sa.Float()),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
    )
    for category in ("popular", "rising", "emerging"):
        op.create_index(
            f"ix_trends_{category}",
            "trend_snapshots",
            ["window_minutes", "language", f"{category}_score", "topic_id"],
        )
    op.create_table(
        "trend_state",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("last_processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True)),
        sa.Column("posts_processed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("errors", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("backlog", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("processing_ms", sa.Float()),
        sa.Column("query_ms", sa.Float()),
        sa.Column("ranking_ms", sa.Float()),
        sa.Column("coverage_warnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topics_discovered", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO trend_state(id, status) VALUES ('bluesky', 'not_started')")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(PG_TRIGGER)
        op.execute(
            "CREATE TRIGGER trendsky_post_insert AFTER INSERT ON posts "
            "FOR EACH ROW EXECUTE FUNCTION trendsky_post_changed()"
        )
        op.execute(
            "CREATE TRIGGER trendsky_post_mutate BEFORE UPDATE OR DELETE ON posts "
            "FOR EACH ROW EXECUTE FUNCTION trendsky_post_changed()"
        )
    elif op.get_bind().dialect.name == "sqlite":
        for operation in ("INSERT", "UPDATE", "DELETE"):
            ref = "OLD" if operation == "DELETE" else "NEW"
            invalidation = (
                ""
                if operation == "INSERT"
                else """
              UPDATE topics SET revision = revision + 1 WHERE id IN
                (SELECT topic_id FROM post_topics WHERE post_uri = OLD.uri);
              DELETE FROM trend_snapshots WHERE EXISTS
                (SELECT 1 FROM post_topics p WHERE p.post_uri=OLD.uri
                  AND p.topic_id=trend_snapshots.topic_id AND p.activity_at<trend_snapshots.as_of);
              DELETE FROM topics WHERE id IN
                (SELECT topic_id FROM post_topics WHERE post_uri = OLD.uri)
                AND NOT EXISTS (SELECT 1 FROM post_topics p
                  WHERE p.topic_id=topics.id AND p.post_uri<>OLD.uri);
              DELETE FROM post_topics WHERE post_uri = OLD.uri;
            """
            )
            timing = "AFTER" if operation == "INSERT" else "BEFORE"
            op.execute(f"""
              CREATE TRIGGER trendsky_post_{operation.lower()} {timing} {operation} ON posts BEGIN
                {invalidation}
                INSERT INTO topic_jobs(post_uri,generation,touched_at)
                  VALUES ({ref}.uri,1,CURRENT_TIMESTAMP)
                  ON CONFLICT(post_uri) DO UPDATE
                    SET generation=generation+1,touched_at=excluded.touched_at;
              END
            """)
    # Install capture before seeding. PG holds its trigger DDL lock until commit, so
    # no source mutation can fall between the initial scan and change capture.
    op.execute(
        "INSERT INTO topic_jobs(post_uri,generation,touched_at) SELECT uri,1,ingested_at FROM posts"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER trendsky_post_insert ON posts")
        op.execute("DROP TRIGGER trendsky_post_mutate ON posts")
        op.execute("DROP FUNCTION trendsky_post_changed()")
    elif op.get_bind().dialect.name == "sqlite":
        for operation in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER trendsky_post_{operation}")
    for table in ("trend_state", "trend_snapshots", "post_topics", "topic_jobs", "topics"):
        op.drop_table(table)
