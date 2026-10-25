from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase

from trendsky_api.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().sqlalchemy_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 3},
    )
