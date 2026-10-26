import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from trendsky_api.database import Base
from trendsky_api.models import DataSource  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


def run_migration_contract(engine, monkeypatch):
    monkeypatch.setattr("trendsky_api.database.get_engine", lambda: engine)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # No duplicate seed or schema changes.
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM data_sources")).scalar_one() == 1
        assert connection.execute(
            text("SELECT collection_status FROM data_sources")
        ).scalar_one() == ("not_started")
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0003_trends"
        )
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(config, "base")
    assert "data_sources" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")


def test_migration_contract_sqlite(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'contract.db'}")
    run_migration_contract(engine, monkeypatch)
    engine.dispose()


@pytest.mark.postgres
def test_migration_contract_postgres(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; PostgreSQL verification requires a disposable DB"
        )
    # This contract intentionally downgrades the schema. Never point at operational data.
    engine = create_engine(url)
    run_migration_contract(engine, monkeypatch)
    engine.dispose()
