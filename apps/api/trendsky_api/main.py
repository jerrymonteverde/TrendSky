import logging
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from trendsky_api.config import get_settings
from trendsky_api.database import get_engine
from trendsky_api.models import DataSource
from trendsky_api.schemas import CollectionSummary, Health

logger = logging.getLogger("trendsky.api")


class RateLimitMiddleware:
    """Bounded per-process fixed windows. Use an edge limiter when scaling workers."""

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit
        self.windows: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self.lock = Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in {"/api/v1/health", "/api/v1/live"}:
            await self.app(scope, receive, send)
            return
        # Ignore user-controlled forwarding headers.
        key = str(scope.get("client", ("unknown",))[0])
        now = time.monotonic()
        with self.lock:
            start, count = self.windows.get(key, (now, 0))
            if now - start >= 60:
                start, count = now, 0
            self.windows[key] = (start, count + 1)
            self.windows.move_to_end(key)
            if len(self.windows) > 10000:
                self.windows.popitem(last=False)
        if count >= self.limit:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again shortly."},
                headers={"Retry-After": str(max(1, int(60 - (now - start))))},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    if get_engine.cache_info().currsize:
        await run_in_threadpool(get_engine().dispose)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="TrendSky API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database_unavailable", extra={"path": request.url.path})
        return JSONResponse(status_code=503, content={"detail": "Data service unavailable."})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": "Invalid request parameters."})

    @app.get("/api/v1/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/health", response_model=Health)
    def health(response: Response) -> Health:
        database = "unavailable"
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
                database = "connected"
                source = connection.execute(
                    select(DataSource.id).where(DataSource.id == "bluesky")
                ).scalar_one()
                revision = connection.execute(text("SELECT version_num FROM alembic_version"))
                if source and revision.scalar_one() == "0001_sources":
                    return Health(status="ok", database="connected", schema_status="ready")
        except SQLAlchemyError:
            logger.warning("readiness_failed")
        response.status_code = 503
        return Health(
            status="unavailable",
            database="connected" if database == "connected" else "unavailable",
            schema_status="unavailable",
        )

    @app.get("/api/v1/analytics/summary", response_model=CollectionSummary)
    def summary() -> CollectionSummary:
        with get_engine().connect() as connection:
            connection.execute(select(DataSource.id).where(DataSource.id == "bluesky")).scalar_one()
        return CollectionSummary()

    return app


app = create_app()
