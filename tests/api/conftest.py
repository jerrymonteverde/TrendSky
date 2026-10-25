import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from trendsky_api.config import get_settings
from trendsky_api.database import Base
from trendsky_api.main import create_app
from trendsky_api.models import DataSource


@pytest.fixture
def client(monkeypatch):
    """Deterministic transport/database tests; PostgreSQL has a separate contract test."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "120")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            DataSource.__table__.insert(),
            {
                "id": "bluesky",
                "name": "Bluesky",
                "collection_status": "not_started",
            },
        )
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0001_sources')")
    monkeypatch.setattr("trendsky_api.main.get_engine", lambda: engine)
    # Use TestClient without lifespan; engine teardown is owned by this fixture.
    yield TestClient(create_app())
    engine.dispose()
    get_settings.cache_clear()
