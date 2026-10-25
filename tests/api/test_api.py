from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from trendsky_api.config import Settings, get_settings
from trendsky_api.main import create_app


def test_liveness_and_readiness(client):
    assert client.get("/api/v1/live").json() == {"status": "ok"}
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "schema_status": "ready",
        "version": "0.1.0",
    }


def test_summary_does_not_imply_zero_activity(client):
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    assert response.json()["collection_status"] == "not_started"
    assert response.json()["observed_posts"] is None
    assert response.json()["collection_started_at"] is None
    assert response.json()["latest_event_at"] is None


def test_database_failure_has_safe_errors(client, monkeypatch):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError(
        "private connection data", {}, Exception("secret")
    )
    monkeypatch.setattr("trendsky_api.main.get_engine", lambda: engine)
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 503
    assert response.json() == {"detail": "Data service unavailable."}
    assert "secret" not in response.text


def test_readiness_detects_unmigrated_database(client, monkeypatch):
    engine = create_engine("sqlite://")
    monkeypatch.setattr("trendsky_api.main.get_engine", lambda: engine)
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["database"] == "connected"
    assert response.json()["schema_status"] == "unavailable"
    engine.dispose()


def test_cors_allows_only_configured_origin(client):
    assert (
        client.get("/api/v1/live", headers={"Origin": "http://localhost:3000"}).headers[
            "access-control-allow-origin"
        ]
        == "http://localhost:3000"
    )
    assert (
        "access-control-allow-origin"
        not in client.get("/api/v1/live", headers={"Origin": "https://untrusted.example"}).headers
    )


def test_rate_limit_and_health_exemption(client, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    limited = TestClient(create_app())
    assert limited.get("/api/v1/analytics/summary").status_code == 200
    assert limited.get("/api/v1/analytics/summary").status_code == 200
    response = limited.get("/api/v1/analytics/summary")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert limited.get("/api/v1/live").status_code == 200


def test_openapi_exposes_only_implemented_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/analytics/summary" in paths
    assert "/api/v1/trending" not in paths


def test_database_password_is_escaped_and_redacted():
    from pydantic import SecretStr

    settings = Settings(_env_file=None, app_db_password=SecretStr("p@ss:/?#word"))
    url = settings.sqlalchemy_url()
    assert url.password == "p@ss:/?#word"
    assert "p@ss" not in repr(settings)
