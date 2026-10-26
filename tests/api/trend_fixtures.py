"""Synthetic, reproducible scenarios. Never used by the public application."""

from datetime import timedelta

from sqlalchemy import insert, update
from trendsky_api.models import CollectionCoverage, IngestionState, Post

SCENARIOS = {
    "steady": [12, 12, 12, 12, 12, 12, 12, 12],
    "rocket": [20, 8, 12, 12, 12, 12, 12, 12],
    "declining": [4, 12, 12, 12, 12, 12, 12, 12],
    "newtopic": [10, 0, 0, 0, 0, 0, 0, 0],
    "oneaccount": [50, 4, 4, 4, 4, 4, 4, 4],
    "deletedtopic": [8, 8, 8, 8, 8, 8, 8, 8],
}


def seed_scenarios(engine, asof, now):
    rows = []
    sequence = 1
    for label, counts in SCENARIOS.items():
        for slot, count in enumerate(counts):
            activity = asof - timedelta(minutes=slot * 5 + 2)
            for index in range(count):
                author = 0 if label == "oneaccount" else index % 10
                rows.append(
                    {
                        "uri": f"at://did:synthetic:{author}/app.bsky.feed.post/{label}-{slot}-{index}",
                        "did": f"did:synthetic:{author}",
                        "rkey": f"{label}-{slot}-{index}",
                        "text": f"#{label}",
                        "created_at": activity,
                        "event_at": activity,
                        "ingested_at": now,
                        "event_seq": sequence,
                        "languages": ["en"],
                    }
                )
                sequence += 1
    with engine.begin() as connection:
        connection.execute(insert(Post), rows)
        connection.execute(
            update(IngestionState).values(
                status="collecting",
                collection_started_at=asof - timedelta(days=3),
                heartbeat_at=now,
                last_event_at=now,
                last_persisted_at=now,
            )
        )
        connection.execute(
            insert(CollectionCoverage).values(
                source_id="bluesky", started_at=asof - timedelta(days=3), outcome="collecting"
            )
        )
    return len(rows)
