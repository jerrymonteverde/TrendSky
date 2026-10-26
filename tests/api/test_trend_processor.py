from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, insert, select, update
from trend_fixtures import seed_scenarios
from trendsky_api.config import Settings
from trendsky_api.ingestion.store import IngestionStore
from trendsky_api.models import CoverageGap, Post
from trendsky_api.trends.extraction import topic
from trendsky_api.trends.models import PostTopic, TopicJob, TrendSnapshot
from trendsky_api.trends.processor import process_batch, refresh


def run_all(engine, settings, now):
    while process_batch(engine, settings, now):
        pass
    return refresh(engine, settings, now)


def get_metrics(engine, label, language="all"):
    with engine.connect() as connection:
        return connection.execute(
            select(TrendSnapshot.metrics).where(
                TrendSnapshot.topic_id == topic("hashtag", label).id,
                TrendSnapshot.window_minutes == 5,
                TrendSnapshot.language == language,
            )
        ).scalar_one()


def test_synthetic_scenarios_sql_aggregation_and_restart(analytical_db):
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    asof = now - timedelta(minutes=1)
    count = seed_scenarios(analytical_db, asof, now)
    settings = Settings(_env_file=None, trends_batch_size=100)
    results = run_all(analytical_db, settings, now)
    assert len(results) == 5
    steady = get_metrics(analytical_db, "steady")
    assert steady["current_activity"] == 12
    assert steady["unique_contributors"] == 10
    assert steady["previous_activity"] == 12
    assert steady["growth_percent"] == 0
    assert steady["trend_status"] == "Stable"
    assert get_metrics(analytical_db, "rocket")["growth_percent"] == 150
    assert get_metrics(analytical_db, "rocket")["trend_status"] == "Rising"
    assert get_metrics(analytical_db, "declining")["trend_status"] == "Declining"
    assert get_metrics(analytical_db, "newtopic")["trend_status"] == "Emerging"
    assert get_metrics(analytical_db, "newtopic")["growth_percent"] is None
    assert get_metrics(analytical_db, "steady", "en")["current_activity"] == 12
    assert process_batch(analytical_db, settings, now) == 0
    run_all(analytical_db, settings, now)
    assert get_metrics(analytical_db, "steady")["current_activity"] == 12
    with analytical_db.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Post)).scalar_one() == count
        assert (
            connection.execute(
                select(func.count())
                .select_from(TrendSnapshot)
                .where(TrendSnapshot.topic_id == topic("hashtag", "oneaccount").id)
            ).scalar_one()
            == 0
        )


def test_updates_deletes_and_retention_invalidate_and_recalculate(analytical_db):
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    asof = now - timedelta(minutes=1)
    seed_scenarios(analytical_db, asof, now)
    settings = Settings(_env_file=None)
    run_all(analytical_db, settings, now)
    identifier = topic("hashtag", "deletedtopic").id
    with analytical_db.begin() as connection:
        uris = (
            connection.execute(
                select(Post.uri).where(Post.rkey.in_([f"deletedtopic-0-{i}" for i in range(3)]))
            )
            .scalars()
            .all()
        )
        connection.execute(delete(Post).where(Post.uri.in_(uris)))
        assert (
            connection.execute(
                select(func.count())
                .select_from(TrendSnapshot)
                .where(TrendSnapshot.topic_id == identifier)
            ).scalar_one()
            == 0
        )
    run_all(analytical_db, settings, now)
    value = get_metrics(analytical_db, "deletedtopic")
    assert value["current_activity"] == 5
    assert value["growth_percent"] == -37.5
    with analytical_db.begin() as connection:
        connection.execute(
            update(Post).where(Post.rkey == "steady-0-0").values(text="#edited", event_seq=100000)
        )
    run_all(analytical_db, settings, now)
    assert get_metrics(analytical_db, "steady")["current_activity"] == 11
    with analytical_db.begin() as connection:
        connection.execute(delete(Post).where(Post.text == "#edited"))
        assert (
            connection.execute(
                select(func.count())
                .select_from(PostTopic)
                .where(PostTopic.topic_id == topic("hashtag", "edited").id)
            ).scalar_one()
            == 0
        )


def test_partial_coverage_nulls_growth_and_history(analytical_db):
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    asof = now - timedelta(minutes=1)
    seed_scenarios(analytical_db, asof, now)
    with analytical_db.begin() as connection:
        connection.execute(
            CoverageGap.__table__.insert().values(
                source_id="bluesky",
                detected_at=asof - timedelta(minutes=2),
                gap_start_at=asof - timedelta(minutes=3),
                reason="synthetic_invalid_frame",
            )
        )
    run_all(analytical_db, Settings(_env_file=None), now)
    value = get_metrics(analytical_db, "rocket")
    assert value["growth_percent"] is None
    assert value["coverage_status"] == "partial_coverage"
    assert value["history"][-1]["posts"] is None
    assert value["rising_score"] is None


def test_migration_queue_is_incremental_and_source_rows_survive(analytical_db):
    now = datetime.now(UTC)
    seed_scenarios(analytical_db, now - timedelta(minutes=1), now)
    with analytical_db.connect() as connection:
        assert connection.execute(select(func.count()).select_from(TopicJob)).scalar_one() > 0


def test_new_and_late_posts_use_event_time_and_preserve_valid_snapshots(analytical_db):
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    asof = now - timedelta(minutes=1)
    seed_scenarios(analytical_db, asof, now)
    settings = Settings(_env_file=None)
    run_all(analytical_db, settings, now)
    with analytical_db.begin() as connection:
        base = dict(
            connection.execute(select(Post.__table__).where(Post.rkey == "steady-0-0"))
            .mappings()
            .one()
        )
        base.update(
            uri="at://synthetic/new",
            rkey="new",
            did="did:synthetic:new",
            event_seq=100001,
            created_at=now,
            event_at=now,
        )
        connection.execute(insert(Post), base)
    assert process_batch(analytical_db, settings, now) == 1
    assert get_metrics(analytical_db, "steady")["current_activity"] == 12
    with analytical_db.begin() as connection:
        base.update(
            uri="at://synthetic/late",
            rkey="late",
            event_seq=100002,
            created_at=asof - timedelta(minutes=5),
            event_at=now,
        )
        connection.execute(insert(Post), base)
    run_all(analytical_db, settings, now)
    assert get_metrics(analytical_db, "steady")["current_activity"] == 13
    with analytical_db.begin() as connection:
        connection.execute(
            update(Post)
            .where(Post.uri == "at://synthetic/late")
            .values(ingested_at=now - timedelta(days=31))
        )
    assert IngestionStore(analytical_db).cleanup_retention(30) == 1
    run_all(analytical_db, settings, now)
    assert get_metrics(analytical_db, "steady")["current_activity"] == 12


def test_all_language_contributors_are_distinct_across_declared_languages(analytical_db):
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    asof = now - timedelta(minutes=1)
    seed_scenarios(analytical_db, asof, now)
    with analytical_db.begin() as connection:
        rows = []
        for i in range(12):
            rows.append(
                {
                    "uri": f"at://synthetic/multi/{i}",
                    "rkey": f"multi{i}",
                    "did": f"did:synthetic:{i % 3}",
                    "text": "#multilingual",
                    "created_at": asof - timedelta(minutes=2),
                    "event_at": now,
                    "ingested_at": now,
                    "event_seq": 100000 + i,
                    "languages": ["en" if i < 6 else "es"],
                }
            )
        connection.execute(insert(Post), rows)
    run_all(analytical_db, Settings(_env_file=None), now)
    assert get_metrics(analytical_db, "multilingual")["unique_contributors"] == 3
    assert get_metrics(analytical_db, "multilingual")["contributor_capped_activity"] == 9
    assert get_metrics(analytical_db, "multilingual", "en")["unique_contributors"] == 3
    assert get_metrics(analytical_db, "multilingual", "es")["current_activity"] == 6


def test_upgrade_seeds_queue_without_replacing_existing_observations(analytical_db):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.downgrade(config, "0002_ingestion")
    now = datetime.now(UTC)
    with analytical_db.begin() as connection:
        connection.execute(
            insert(Post).values(
                uri="at://synthetic/preserved",
                did="did:synthetic:author",
                rkey="preserved",
                text="public text preserved",
                event_at=now,
                ingested_at=now,
                event_seq=123,
            )
        )
    command.upgrade(config, "head")
    with analytical_db.connect() as connection:
        assert connection.execute(select(Post.text)).scalar_one() == "public text preserved"
        assert (
            connection.execute(select(TopicJob.post_uri)).scalar_one() == "at://synthetic/preserved"
        )


def test_candidate_cap_and_tied_ranks_are_deterministic(analytical_db):
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    asof = now - timedelta(minutes=1)
    seed_scenarios(analytical_db, asof, now)
    with analytical_db.begin() as connection:
        connection.execute(
            insert(Post),
            [
                {
                    "uri": f"at://synthetic/tie/{label}/{i}",
                    "rkey": f"tie{label}-{i}",
                    "did": f"did:synthetic:tie{i % 3}",
                    "text": f"#candidate{label}",
                    "created_at": asof - timedelta(minutes=2),
                    "event_at": now,
                    "ingested_at": now,
                    "event_seq": 200000 + label * 6 + i,
                    "languages": ["en"],
                }
                for label in range(20)
                for i in range(6)
            ],
        )
    settings = Settings(_env_file=None, trends_max_topics=10)
    run_all(analytical_db, settings, now)
    with analytical_db.connect() as connection:
        ids = (
            connection.execute(
                select(TrendSnapshot.topic_id).where(
                    TrendSnapshot.window_minutes == 5, TrendSnapshot.language == "all"
                )
            )
            .scalars()
            .all()
        )
        assert len(ids) == 10
        tied = (
            connection.execute(
                select(TrendSnapshot.topic_id)
                .where(
                    TrendSnapshot.window_minutes == 5,
                    TrendSnapshot.language == "all",
                    TrendSnapshot.current_posts == 6,
                    TrendSnapshot.unique_contributors == 3,
                )
                .order_by(TrendSnapshot.popular_score.desc(), TrendSnapshot.topic_id)
            )
            .scalars()
            .all()
        )
        assert len(tied) > 1 and tied == sorted(tied)
