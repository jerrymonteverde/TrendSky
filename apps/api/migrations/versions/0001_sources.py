"""Create the source registry without fabricating any observations."""

import sqlalchemy as sa
from alembic import op

revision = "0001_sources"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    sources = op.create_table(
        "data_sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("collection_status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "collection_status IN ('not_started', 'collecting', 'paused')",
            name="ck_data_sources_status",
        ),
    )
    op.bulk_insert(
        sources, [{"id": "bluesky", "name": "Bluesky", "collection_status": "not_started"}]
    )


def downgrade() -> None:
    op.drop_table("data_sources")
