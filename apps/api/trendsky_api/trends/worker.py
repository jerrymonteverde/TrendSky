"""Independent, resource-bounded trends process: python -m trendsky_api.trends.worker."""

import logging
import signal
import threading
import time
from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from trendsky_api.config import get_settings
from trendsky_api.observability import configure_logging, error_fields, safe_error
from trendsky_api.trends.models import TopicJob, TrendState
from trendsky_api.trends.processor import process_batch, refresh

logger = logging.getLogger("trendsky.trends")


def main() -> None:
    configure_logging()
    settings = get_settings()
    engine = create_engine(
        settings.sqlalchemy_url(),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        pool_timeout=5,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    next_refresh = 0.0
    failures = 0
    blocked = False
    try:
        while not stop.is_set():
            phase = "trend_status"
            try:
                if not settings.trends_enabled:
                    with engine.begin() as connection:
                        connection.execute(
                            update(TrendState)
                            .where(TrendState.id == "bluesky")
                            .values(status="disabled", heartbeat_at=datetime.now(UTC))
                        )
                    stop.wait(30)
                    continue
                phase = "topic_batch"
                processed = process_batch(engine, settings)
                if time.monotonic() >= next_refresh:
                    phase = "trend_refresh"
                    results = refresh(engine, settings)
                    logger.info("trend_refresh", extra={"windows": results})
                    next_refresh = time.monotonic() + settings.trends_refresh_seconds
                phase = "trend_status"
                with engine.begin() as connection:
                    backlog = connection.execute(
                        select(func.count()).select_from(TopicJob)
                    ).scalar_one()
                    connection.execute(
                        update(TrendState)
                        .where(TrendState.id == "bluesky")
                        .values(heartbeat_at=datetime.now(UTC), backlog=backlog)
                    )
                if processed:
                    logger.info(
                        "topic_batch", extra={"posts_processed": processed, "backlog": backlog}
                    )
                failures = 0
                stop.wait(settings.trends_batch_pause_seconds if backlog else 1)
            except Exception as exc:
                failures += 1
                info = safe_error(exc, phase)
                fields = error_fields(exc)
                fields["error"] = info.__dict__
                logger.error(
                    "trend_processing_error", extra={**fields, "attempt": failures, "phase": phase}
                )
                try:
                    with engine.begin() as connection:
                        connection.execute(
                            update(TrendState)
                            .where(TrendState.id == "bluesky")
                            .values(
                                status="error",
                                errors=TrendState.errors + 1,
                                heartbeat_at=datetime.now(UTC),
                            )
                        )
                except SQLAlchemyError:
                    pass
                if not info.retryable:
                    blocked = True
                    stop.wait()
                    break
                stop.wait(min(30, 2 ** min(failures, 5)))
    finally:
        if not blocked:
            try:
                with engine.begin() as connection:
                    connection.execute(
                        update(TrendState)
                        .where(TrendState.id == "bluesky")
                        .values(status="stopped", heartbeat_at=datetime.now(UTC))
                    )
            except SQLAlchemyError as exc:
                logger.error("trend_shutdown_status_failed", extra=error_fields(exc))
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.critical("trend_startup_failed", extra=error_fields(exc))
        raise SystemExit(1) from None
