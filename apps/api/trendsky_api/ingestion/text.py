"""PostgreSQL-bound string compatibility; stable identifiers are validated, never rewritten."""

import re

SURROGATE = re.compile(r"[\ud800-\udfff]")


class RecordValidationError(ValueError):
    """Only a safe reason code is carried; never the rejected field value."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.safe_reason = reason


def postgres_text(value: str) -> str:
    value = value.replace("\x00", "\ufffd")
    if SURROGATE.search(value):
        # Preserve legitimate surrogate pairs; replace only malformed scalar sequences.
        value = value.encode("utf-16-le", errors="surrogatepass").decode(
            "utf-16-le", errors="replace"
        )
    return value


def validate_identifier(value: str | None, limit: int) -> None:
    if (
        value is None
        or not value
        or len(value) > limit
        or "\x00" in value
        or SURROGATE.search(value)
    ):
        raise RecordValidationError("unsupported_record_identifier")
