"""Async Jetstream v2 reader with bounded buffering and transactional checkpoints."""

from __future__ import annotations

import asyncio
import logging
import random
import signal
import time
import uuid
from collections import deque
from collections.abc import Callable
from typing import Any

import websockets
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from trendsky_api.config import get_settings
from trendsky_api.ingestion.failures import (
    BatchFailure,
    PersistenceBlocked,
    PersistenceRetryExhausted,
    parse_failure,
)
from trendsky_api.ingestion.protocol import (
    FrameError,
    JetstreamInfo,
    build_subscription_url,
    parse_frame,
)
from trendsky_api.ingestion.store import IngestionStore, IngestItem, InvalidFrame
from trendsky_api.observability import configure_logging, error_fields, safe_error

logger = logging.getLogger("trendsky.ingestion")


class StopToken:
    """Queue sentinel distinct from valid event items."""


STOP = StopToken()
Connect = Callable[..., Any]


class CursorExpired(RuntimeError):
    """The configured Jetstream host can no longer replay the stored cursor."""


class RateWindow:
    """Bounded 60-second event-count window; memory is capped at one item per second."""

    def __init__(self) -> None:
        self._buckets: deque[tuple[int, int]] = deque(maxlen=61)
        self._started = time.monotonic()
        self.last_commit_at = 0.0

    def record(self, count: int) -> None:
        if count <= 0:
            return
        second = int(time.monotonic())
        if self._buckets and self._buckets[-1][0] == second:
            previous_second, previous_count = self._buckets.pop()
            self._buckets.append((previous_second, previous_count + count))
        else:
            self._buckets.append((second, count))

    def per_minute(self) -> float:
        now = int(time.monotonic())
        floor = now - 59
        while self._buckets and self._buckets[0][0] < floor:
            self._buckets.popleft()
        observed_seconds = min(60, max(1, int(time.monotonic() - self._started)))
        return round(sum(count for _, count in self._buckets) * 60 / observed_seconds, 2)


def is_cursor_too_old(error: BaseException) -> bool:
    """Recognize Jetstream's pre-upgrade HTTP 400 XRPC CursorTooOld response."""
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    body = getattr(response, "body", b"")
    headers = getattr(response, "headers", {})
    detail = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    if not detail:
        detail = str(error)
    if headers:
        detail = f"{detail} {headers}"
    return status == 400 and "cursortooold" in detail.casefold().replace(
        "cursor_too_old", "cursortooold"
    )


async def _persist_batch(
    store: IngestionStore,
    batch: list[IngestItem],
    rate: RateWindow,
    flush_interval_ms: int,
) -> None:
    delay = max(0.1, flush_interval_ms / 1000)
    identifier = uuid.uuid4().hex[:12]
    sequences = [item.seq for item in batch if item.seq is not None and 0 <= item.seq < 2**63]
    for attempt in range(5):
        try:
            result = await asyncio.to_thread(store.persist_batch, batch, rate.per_minute())
            rate.record(result["posts_written"])
            rate.last_commit_at = time.monotonic()
            return
        except Exception as exc:
            info = safe_error(exc)
            failure = BatchFailure(
                identifier,
                len(batch),
                min(sequences, default=None),
                max(sequences, default=None),
                info.category,
                info.sqlstate,
                info.phase,
                blocked=not info.retryable,
            )
            fields = {
                **error_fields(exc),
                "batch_id": identifier,
                "batch_size": len(batch),
                "seq_min": failure.seq_min,
                "seq_max": failure.seq_max,
                "attempt": attempt + 1,
                "phase": info.phase,
            }
            if not info.retryable:
                try:
                    await asyncio.to_thread(store.record_batch_failure, failure)
                except Exception as state_error:
                    logger.error(
                        "failure_marker_persistence_failed", extra=error_fields(state_error)
                    )
                logger.error("batch_persistence_blocked", extra=fields)
                raise PersistenceBlocked(failure, info) from exc
            if attempt == 4:
                with suppress_database_error():
                    await asyncio.to_thread(store.record_processing_error, type(exc).__name__)
                logger.error("batch_persistence_failed", extra=fields)
                raise PersistenceRetryExhausted(failure, info) from exc
            retry_seconds = min(8.0, delay * (2**attempt)) * random.uniform(0.8, 1.2)
            logger.warning(
                "batch_persistence_retry",
                extra={**fields, "retry_seconds": round(retry_seconds, 3)},
            )
            await asyncio.sleep(retry_seconds)


class suppress_database_error:
    """Avoid masking the original transaction failure if metric persistence also fails."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return isinstance(exc, SQLAlchemyError)


async def _writer(
    queue: asyncio.Queue[IngestItem | StopToken],
    store: IngestionStore,
    rate: RateWindow,
    batch_size: int,
    flush_interval_ms: int,
) -> None:
    flush_seconds = flush_interval_ms / 1000
    while True:
        item = await queue.get()
        if isinstance(item, StopToken):
            queue.task_done()
            return
        batch = [item]
        sentinel_seen = False
        deadline = asyncio.get_running_loop().time() + flush_seconds
        while len(batch) < batch_size:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                extra = await asyncio.wait_for(queue.get(), timeout=remaining)
            except TimeoutError:
                break
            if isinstance(extra, StopToken):
                sentinel_seen = True
                queue.task_done()
                break
            batch.append(extra)
        await _persist_batch(store, batch, rate, flush_interval_ms)
        for _ in batch:
            queue.task_done()
        if sentinel_seen:
            return


async def _receiver(
    websocket: Any,
    queue: asyncio.Queue[IngestItem | StopToken],
    store: IngestionStore,
) -> None:
    async for frame in websocket:
        try:
            event = parse_frame(frame)
        except FrameError as exc:
            logger.warning(
                "jetstream_frame_rejected",
                extra={"reason": str(exc), "has_seq": exc.seq is not None},
            )
            if exc.seq is None:
                await asyncio.to_thread(store.record_unsequenced_invalid, str(exc))
            else:
                await queue.put(InvalidFrame(exc.seq, str(exc)))
            continue
        if isinstance(event, JetstreamInfo):
            logger.warning(
                "jetstream_info",
                extra={
                    "name": event.name
                    if event.name in {"CursorTooOld", "OutdatedCursor"}
                    else "other"
                },
            )
            await asyncio.to_thread(store.record_info, event.name, event.message)
            if event.name in {"CursorTooOld", "OutdatedCursor"}:
                raise CursorExpired(event.name)
        else:
            await queue.put(event)


async def _connection_session(
    store: IngestionStore,
    settings: Any,
    stop: asyncio.Event,
    rate: RateWindow,
    connect: Connect,
) -> None:
    state = await asyncio.to_thread(store.load_state)
    cursor = state["last_seq"]
    url = build_subscription_url(settings.jetstream_url, cursor)
    queue: asyncio.Queue[IngestItem | StopToken] = asyncio.Queue(
        maxsize=settings.ingestion_queue_max_size
    )
    await asyncio.to_thread(store.mark_connecting)
    async with connect(
        url,
        subprotocols=["xrpc.v1.json"],
        open_timeout=10,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
        max_size=1_048_576,
        max_queue=32,
        write_limit=32_768,
    ) as websocket:
        if websocket.subprotocol != "xrpc.v1.json":
            raise ConnectionError(
                "Jetstream did not negotiate the required xrpc.v1.json subprotocol."
            )
        await asyncio.to_thread(store.mark_connected)
        writer_task = asyncio.create_task(
            _writer(
                queue,
                store,
                rate,
                settings.ingestion_batch_size,
                settings.ingestion_flush_interval_ms,
            ),
            name="ingestion-batch-writer",
        )
        receiver_task = asyncio.create_task(
            _receiver(websocket, queue, store), name="jetstream-reader"
        )
        stop_task = asyncio.create_task(stop.wait(), name="ingestion-stop-waiter")
        heartbeat_task = asyncio.create_task(
            _heartbeat(store, settings, rate, stop), name="ingestion-heartbeat"
        )
        try:
            done, _ = await asyncio.wait(
                {receiver_task, writer_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if writer_task in done:
                await writer_task
            if stop_task in done:
                await websocket.close(code=1001, reason="TrendSky ingestion shutting down")
                if not receiver_task.done():
                    receiver_task.cancel()
            elif receiver_task in done:
                await receiver_task
            if not writer_task.done():
                await queue.put(STOP)
                await writer_task
        finally:
            for task in (receiver_task, stop_task, heartbeat_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(receiver_task, stop_task, heartbeat_task, return_exceptions=True)
            if not writer_task.done():
                writer_task.cancel()
                await asyncio.gather(writer_task, return_exceptions=True)


async def _heartbeat(
    store: IngestionStore, settings: Any, rate: RateWindow, stop: asyncio.Event
) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.ingestion_heartbeat_interval_seconds
            )
        except TimeoutError:
            try:
                await asyncio.to_thread(store.heartbeat, rate.per_minute())
            except SQLAlchemyError as exc:
                logger.error("ingestion_heartbeat_failed", extra=error_fields(exc))


async def _retention_loop(store: IngestionStore, settings: Any, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=3600)
        except TimeoutError:
            try:
                removed = await asyncio.to_thread(
                    store.cleanup_retention, settings.ingestion_retention_days
                )
                if removed:
                    logger.info("retention_cleanup_completed", extra={"posts_removed": removed})
            except SQLAlchemyError as exc:
                logger.error("retention_cleanup_failed", extra=error_fields(exc))


async def run_worker(
    store: IngestionStore,
    settings: Any,
    stop: asyncio.Event,
    connect: Connect = websockets.connect,
) -> None:
    """Run forever unless stopped or blocked on a cursor that needs operator recovery."""
    state = None
    startup_attempts = 0
    while state is None and not stop.is_set():
        try:
            state = await asyncio.to_thread(store.load_state)
        except Exception as exc:
            info = safe_error(exc)
            logger.error("ingestion_startup_state_failed", extra=error_fields(exc))
            if not info.retryable:
                await stop.wait()
                return
            startup_attempts += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=min(60, 2 ** min(startup_attempts, 6)))
            except TimeoutError:
                pass
    if state is None:
        return
    persisted_failure = parse_failure(state.get("last_error"))
    if persisted_failure is not None and persisted_failure.blocked:
        logger.error(
            "ingestion_operator_review_required", extra={"batch_id": persisted_failure.batch_id}
        )
        await stop.wait()
        return
    if not settings.ingestion_enabled:
        await asyncio.to_thread(
            store.mark_status, "not_started", "Ingestion disabled by configuration."
        )
        await stop.wait()
        return
    if state["cursor_expired"]:
        await asyncio.to_thread(
            store.mark_status,
            "interrupted",
            "Cursor expired previously; operator recovery is required before reconnecting.",
        )
        await stop.wait()
        return

    retention_task = asyncio.create_task(
        _retention_loop(store, settings, stop), name="retention-cleanup"
    )
    rate = RateWindow()
    attempts = 0
    blocked = False
    try:
        while not stop.is_set():
            session_start = time.monotonic()
            try:
                await _connection_session(store, settings, stop, rate, connect)
                if stop.is_set():
                    break
                raise ConnectionError("Jetstream session ended")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if isinstance(exc, CursorExpired) or is_cursor_too_old(exc):
                    logger.error("jetstream_cursor_expired_operator_action_required")
                    await asyncio.to_thread(store.record_cursor_expired)
                    await stop.wait()
                    return
                info = safe_error(exc)
                if isinstance(exc, PersistenceBlocked) or not info.retryable:
                    blocked = True
                    if not isinstance(exc, PersistenceBlocked):
                        failure = BatchFailure(
                            uuid.uuid4().hex[:12],
                            0,
                            None,
                            None,
                            info.category,
                            info.sqlstate,
                            info.phase,
                        )
                        try:
                            await asyncio.to_thread(store.record_batch_failure, failure)
                        except Exception as marker_error:
                            logger.error(
                                "failure_marker_persistence_failed",
                                extra=error_fields(marker_error),
                            )
                    logger.error("ingestion_operator_review_required", extra=error_fields(exc))
                    await stop.wait()
                    return
                if stop.is_set():
                    break
                if rate.last_commit_at > session_start:
                    attempts = 0
                attempts += 1
                delay = min(
                    settings.ingestion_reconnect_max_seconds,
                    settings.ingestion_reconnect_base_seconds * (2 ** min(attempts - 1, 10)),
                ) * random.uniform(0.8, 1.2)
                reason = (
                    exc.failure.encode()
                    if isinstance(exc, PersistenceRetryExhausted)
                    else "Jetstream disconnected; retry scheduled."
                )
                logger.warning(
                    "jetstream_connection_interrupted",
                    extra={
                        "attempt": attempts,
                        "retry_seconds": round(delay, 2),
                        "error_type": type(exc).__name__,
                        **error_fields(exc),
                    },
                )
                try:
                    await asyncio.to_thread(store.mark_status, "reconnecting", reason)
                except SQLAlchemyError as state_error:
                    logger.error("ingestion_status_update_failed", extra=error_fields(state_error))
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except TimeoutError:
                    continue
    finally:
        retention_task.cancel()
        await asyncio.gather(retention_task, return_exceptions=True)
        if not blocked:
            try:
                await asyncio.to_thread(store.mark_status, "interrupted", "Worker stopped cleanly.")
            except SQLAlchemyError as exc:
                logger.error("ingestion_shutdown_status_failed", extra=error_fields(exc))


async def main() -> None:
    configure_logging()
    settings = get_settings()
    engine = create_engine(
        settings.sqlalchemy_url(),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=1,
        pool_timeout=5,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )
    store = IngestionStore(engine)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await run_worker(store, settings, stop)
    except Exception as exc:
        logger.error("ingestion_worker_blocked", extra=error_fields(exc))
        await stop.wait()
    finally:
        await asyncio.to_thread(engine.dispose)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        logger.critical("ingestion_startup_failed", extra=error_fields(exc))
        raise SystemExit(1) from None
