"""Small durable operator-review marker in the existing operational state column."""

import re
from dataclasses import dataclass

from trendsky_api.observability import PHASES, ErrorInfo


@dataclass(frozen=True)
class BatchFailure:
    batch_id: str
    batch_size: int
    seq_min: int | None
    seq_max: int | None
    category: str
    sqlstate: str | None
    phase: str
    blocked: bool = True

    def encode(self) -> str:
        values = (
            "blocked" if self.blocked else "retrying",
            self.sqlstate or "-",
            self.category,
            self.phase,
            self.batch_id,
            str(self.batch_size),
            str(self.seq_min) if self.seq_min is not None else "-",
            str(self.seq_max) if self.seq_max is not None else "-",
        )
        marker = "|".join(values)
        if len(marker) > 160:
            raise ValueError("Failure metadata exceeds the operational state limit.")
        return marker


def parse_failure(marker: str | None) -> BatchFailure | None:
    if not marker:
        return None
    parts = marker.split("|")
    if len(parts) != 8 or parts[0] not in {"blocked", "retrying"}:
        return None
    mode, code, category, phase, identifier, size, low, high = parts
    if not re.fullmatch(r"[a-f0-9]{12}", identifier) or phase not in PHASES:
        return None
    if code != "-" and not re.fullmatch(r"[A-Z0-9]{5}", code):
        return None
    if category not in {
        "data",
        "integrity",
        "schema",
        "unexpected",
        "connection",
        "resource",
        "timeout",
        "pool_timeout",
        "transaction_retry",
        "transaction_state",
        "configuration",
    }:
        return None
    try:
        count = int(size)
        first = None if low == "-" else int(low)
        last = None if high == "-" else int(high)
    except ValueError:
        return None
    if not 0 <= count <= 20000 or any(v is not None and not 0 <= v < 2**63 for v in (first, last)):
        return None
    return BatchFailure(
        identifier,
        count,
        first,
        last,
        category,
        None if code == "-" else code,
        phase,
        mode == "blocked",
    )


class PersistenceBlocked(RuntimeError):
    def __init__(self, failure: BatchFailure, info: ErrorInfo):
        super().__init__("Persistence requires operator review; checkpoint retained.")
        self.failure = failure
        self.safe_info = info


class PersistenceRetryExhausted(RuntimeError):
    def __init__(self, failure: BatchFailure, info: ErrorInfo):
        super().__init__("Transient persistence retries exhausted; checkpoint retained.")
        self.failure = failure
        self.safe_info = info
