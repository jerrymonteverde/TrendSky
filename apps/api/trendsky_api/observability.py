"""Allowlisted operational diagnostics. Never render DB exceptions, SQL or parameters."""

from __future__ import annotations

import json
import logging
import re
import traceback
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.exc import (
    DataError,
    DBAPIError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
)
from sqlalchemy.exc import (
    TimeoutError as PoolTimeout,
)

PHASES = {
    "batch",
    "checkpoint_lock",
    "validation",
    "coverage",
    "deletes",
    "posts",
    "hashtags",
    "hashtag_links",
    "checkpoint",
    "coverage_cursor",
    "commit",
    "topic_batch",
    "trend_refresh",
    "trend_status",
}
MESSAGES = {
    "23505": "unique_constraint_violation",
    "23503": "foreign_key_violation",
    "23514": "check_constraint_violation",
    "23502": "not_null_violation",
    "22001": "value_exceeds_column_limit",
    "22021": "invalid_database_encoding",
    "22P05": "unsupported_database_character",
    "22003": "numeric_out_of_range",
    "40P01": "deadlock_detected",
    "40001": "serialization_failure",
    "55P03": "lock_unavailable",
    "57014": "statement_cancelled_or_timed_out",
    "53100": "disk_full",
    "53200": "database_memory_exhausted",
    "53300": "database_connection_limit",
    "57P01": "database_shutdown",
    "25P02": "transaction_already_aborted",
    "42P01": "database_table_missing",
    "42703": "database_column_missing",
    "42501": "database_permission_denied",
}


@dataclass(frozen=True)
class ErrorInfo:
    exception_type: str
    category: str
    message: str
    sqlstate: str | None
    retryable: bool
    phase: str
    table: str | None = None
    column: str | None = None
    constraint: str | None = None
    http_status: int | None = None


def _identifier(value: Any) -> str | None:
    return (
        value if isinstance(value, str) and re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", value) else None
    )


def safe_error(error: BaseException, phase: str | None = None) -> ErrorInfo:
    """SQLSTATE and structural identifiers only; driver detail/message can contain row values."""
    if isinstance(getattr(error, "safe_info", None), ErrorInfo):
        return error.safe_info  # type: ignore[attr-defined,no-any-return]
    original = getattr(error, "orig", error)
    code = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    code = code if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code) else None
    diagnostic = getattr(original, "diag", None)
    http = getattr(getattr(error, "response", None), "status_code", None)
    http = http if isinstance(http, int) and 100 <= http <= 599 else None
    phase = phase or getattr(error, "trendsky_phase", "batch")
    phase = phase if phase in PHASES else "batch"
    retryable = False
    category = "unexpected"
    if code in {"40P01", "40001"}:
        category, retryable = "transaction_retry", True
    elif code in {"55P03", "57014"}:
        category, retryable = "timeout", True
    elif code and (code.startswith("08") or code in {"57P01", "57P02", "57P03"}):
        category, retryable = "connection", True
    elif code and code.startswith("53"):
        category, retryable = "resource", True
    elif isinstance(error, IntegrityError) or (code and code.startswith("23")):
        category = "integrity"
    elif (
        isinstance(error, DataError)
        or isinstance(original, (UnicodeError, ValueError))
        or (code and code.startswith("22"))
    ):
        category = "data"
    elif isinstance(error, ProgrammingError) or (code and code.startswith("42")):
        category = "schema"
    elif isinstance(error, PoolTimeout):
        category, retryable = "pool_timeout", True
    elif isinstance(error, OperationalError) and code is None:
        category, retryable = "connection", True
    elif isinstance(error, DBAPIError) and error.connection_invalidated:
        category, retryable = "connection", True
    elif code and code.startswith("25"):
        category = "transaction_state"
    elif isinstance(error, PermissionError) or (
        http is not None and 400 <= http < 500 and http != 429
    ):
        category = "configuration"
    elif (
        isinstance(error, (ConnectionError, OSError, TimeoutError))
        or http == 429
        or (http is not None and http >= 500)
        or type(error).__module__.startswith("websockets")
    ):
        category, retryable = "connection", True
    name = type(error).__name__
    reason = getattr(error, "safe_reason", None)
    safe_reason = (
        reason
        if reason
        in {
            "unsupported_record_identifier",
            "unsupported_event_sequence",
            "unsupported_hashtag_length",
        }
        else None
    )
    return ErrorInfo(
        exception_type=name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name) else "Exception",
        category=category,
        message=safe_reason or MESSAGES.get(code or "", f"{category}_failure"),
        sqlstate=code,
        retryable=retryable,
        phase=phase,
        table=_identifier(getattr(diagnostic, "table_name", None)),
        column=_identifier(getattr(diagnostic, "column_name", None)),
        constraint=_identifier(getattr(diagnostic, "constraint_name", None)),
        http_status=http,
    )


def safe_stack(error: BaseException) -> list[dict[str, Any]]:
    # No source lines, locals, exception messages, chained SQL or parameter rendering.
    return [
        {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
        for frame in traceback.extract_tb(error.__traceback__)[-10:]
    ]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        result: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key in (
            "attempt",
            "retry_seconds",
            "batch_size",
            "batch_id",
            "seq_min",
            "seq_max",
            "phase",
            "error",
            "stack",
            "posts_removed",
            "has_seq",
            "reason",
            "name",
            "error_type",
            "posts_processed",
            "backlog",
            "duration_ms",
            "normalized_records",
            "windows",
        ):
            if key in record.__dict__:
                result[key] = record.__dict__[key]
        # Deliberately do not invoke Formatter.formatException even if exc_info is present.
        return json.dumps(result, ensure_ascii=True, default=lambda _: "[unsupported]")


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def error_fields(error: BaseException) -> dict[str, Any]:
    return {"error": asdict(safe_error(error)), "stack": safe_stack(error)}
