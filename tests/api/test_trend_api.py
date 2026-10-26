from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update
from trend_fixtures import seed_scenarios
from trendsky_api.config import Settings
from trendsky_api.models import Post
from trendsky_api.trends.extraction import topic
from trendsky_api.trends.models import TrendSnapshot, TrendState
from trendsky_api.trends.processor import process_batch, refresh


def test_trend_api_empty_and_invalid_parameters(client):
    result = client.get("/api/v1/trending")
    assert result.status_code == 200
    assert result.json()["items"] == []
    assert result.json()["status"] == "not_started"
    assert client.get("/api/v1/trending/status").json()["posts_processed"] == 0
    for query in ["window=42", "language=fr", "limit=0", "offset=-1", "category=unknown"]:
        assert client.get(f"/api/v1/trending?{query}").status_code == 422
    assert client.get("/api/v1/topics/search?q=%").status_code == 200
    assert client.get("/api/v1/topics/search?q=").status_code == 422
    assert client.get("/api/v1/topics/not-valid").status_code == 422
    assert client.get("/api/v1/topics/" + "a" * 64).status_code == 404


def test_api_serves_real_persisted_rankings_and_topic_history(client, analytical_db, monkeypatch):
    monkeypatch.setattr("trendsky_api.main.get_engine", lambda: analytical_db)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    settings = Settings(_env_file=None)
    seed_scenarios(analytical_db, now - timedelta(minutes=1), now)
    while process_batch(analytical_db, settings, now):
        pass
    refresh(analytical_db, settings, now)
    response = client.get("/api/v1/trending/popular?window=5&language=en&limit=2")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_more"]
    assert len(body["items"]) == 2
    assert body["items"][0]["rank"] == 1
    assert all(item["unique_contributors"] >= 3 for item in body["items"])
    assert "did:" not in response.text
    later = client.get("/api/v1/trending?window=5&language=en&offset=2&limit=2").json()
    assert later["items"][0]["rank"] == 3
    assert not {item["topic_id"] for item in later["items"]} & {
        item["topic_id"] for item in body["items"]
    }
    rising = client.get("/api/v1/trending/rising?window=5").json()["items"]
    assert "#rocket" in {item["label"] for item in rising}
    assert "#oneaccount" not in {item["label"] for item in rising}
    emerging = client.get("/api/v1/trending/emerging?window=5").json()["items"]
    assert "#newtopic" in {item["label"] for item in emerging}
    matches = client.get("/api/v1/topics/search?q=%23ste").json()["items"]
    assert matches[0]["label"] == "#steady"
    identifier = topic("hashtag", "steady").id
    detail = client.get(f"/api/v1/topics/{identifier}/activity?window=5").json()
    assert detail["activity"]["current_activity"] == 12
    assert len(detail["activity"]["history"]) == 8
    with analytical_db.begin() as connection:
        connection.execute(delete(Post).where(Post.rkey == "steady-0-0"))
    assert client.get(f"/api/v1/topics/{identifier}").json()["activity"] is None


def test_stale_engine_and_snapshots_are_not_published_as_live(client, analytical_db, monkeypatch):
    monkeypatch.setattr("trendsky_api.main.get_engine", lambda: analytical_db)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    seed_scenarios(analytical_db, now - timedelta(minutes=1), now)
    settings = Settings(_env_file=None)
    while process_batch(analytical_db, settings, now):
        pass
    refresh(analytical_db, settings, now)
    with analytical_db.begin() as connection:
        old = now - timedelta(hours=1)
        connection.execute(update(TrendState).values(heartbeat_at=old, last_calculated_at=old))
        connection.execute(update(TrendSnapshot).values(calculated_at=old))
    assert client.get("/api/v1/trending/status").json()["status"] == "stale"
    assert client.get("/api/v1/trending").json()["items"] == []
    detail = client.get(f"/api/v1/topics/{topic('hashtag', 'steady').id}").json()
    assert detail["status"] == "stale_calculation"
    assert detail["activity"]["growth_percent"] is None


def test_stopped_processor_does_not_publish_recent_snapshots_as_running(
    client, analytical_db, monkeypatch
):
    monkeypatch.setattr("trendsky_api.main.get_engine", lambda: analytical_db)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    seed_scenarios(analytical_db, now - timedelta(minutes=1), now)
    settings = Settings(_env_file=None)
    while process_batch(analytical_db, settings, now):
        pass
    refresh(analytical_db, settings, now)
    with analytical_db.begin() as connection:
        connection.execute(update(TrendState).values(status="stopped"))
    status = client.get("/api/v1/trending/status").json()
    assert status["health"] == "stopped"
    result = client.get("/api/v1/trending").json()
    assert result["status"] == "stopped" and result["items"] == []
    assert "Ingestion status is reported separately" in result["message"]
