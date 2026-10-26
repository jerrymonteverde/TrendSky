import json
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, ProgrammingError
from trendsky_api.observability import JsonFormatter, error_fields, safe_error


class DriverFailure(Exception):
    def __init__(self, code):
        self.sqlstate = code
        self.diag = SimpleNamespace(
            table_name="posts", column_name="text", constraint_name="uq_posts_event_seq"
        )
        super().__init__("secret password private post text postgresql://secret@host")


@pytest.mark.parametrize(
    "code,kind,retry",
    [
        ("23505", "integrity", False),
        ("22001", "data", False),
        ("22P05", "data", False),
        ("42P01", "schema", False),
        ("40P01", "transaction_retry", True),
        ("40001", "transaction_retry", True),
        ("55P03", "timeout", True),
        ("53100", "resource", True),
        ("08006", "connection", True),
    ],
)
def test_classifies_sqlstate_without_rendering_driver_detail(code, kind, retry):
    error = OperationalError("SELECT private SQL", {"text": "private content"}, DriverFailure(code))
    info = safe_error(error, "posts")
    assert info.category == kind
    assert info.retryable is retry
    assert info.sqlstate == code


@pytest.mark.parametrize(
    "error_class", [DataError, IntegrityError, OperationalError, ProgrammingError]
)
def test_json_failure_log_never_contains_sql_parameters_or_exception_message(error_class):
    error = error_class("INSERT secret SQL", {"password": "private text"}, DriverFailure("23505"))
    record = logging.LogRecord(
        "trendsky.ingestion",
        logging.ERROR,
        __file__,
        1,
        "batch_persistence_failed",
        (),
        (type(error), error, None),
    )
    record.__dict__.update(error_fields(error))
    record.batch_id = "a1b2c3"
    value = JsonFormatter().format(record)
    parsed = json.loads(value)
    assert parsed["error"]["sqlstate"] == "23505"
    assert parsed["batch_id"] == "a1b2c3"
    for secret in ("private", "password", "secret", "postgresql://", "INSERT"):
        assert secret not in value
