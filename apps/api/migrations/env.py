from alembic import context
from trendsky_api.database import Base, get_engine
from trendsky_api.models import DataSource  # noqa: F401

target_metadata = Base.metadata

if context.is_offline_mode():
    from trendsky_api.config import get_settings

    context.configure(
        url=get_settings().sqlalchemy_url(),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
