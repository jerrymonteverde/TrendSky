"""Coverage is an observation property, never proof of full Bluesky representation."""

from dataclasses import dataclass
from datetime import UTC, datetime


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class WindowCoverage:
    observed_minutes: float
    fraction: float
    quality: str

    @property
    def complete(self) -> bool:
        return self.quality == "complete_observed_window"


def window_coverage(
    start: datetime,
    end: datetime,
    periods: list[tuple[datetime, datetime]],
    gaps: list[tuple[datetime, datetime]],
    history_start: datetime | None,
) -> WindowCoverage:
    start, end = utc(start), utc(end)
    duration = (end - start).total_seconds()
    intervals = sorted(
        (max(start, utc(a)), min(end, utc(b)))
        for a, b in periods
        if utc(b) > start and utc(a) < end
    )
    merged: list[tuple[datetime, datetime]] = []
    for left, right in intervals:
        if right <= left:
            continue
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    # Subtract known bad intervals from observed time as well as flagging them incomplete.
    known_gap = False
    for left, right in gaps:
        left, right = utc(left), utc(right)
        if left < end and right >= start:
            known_gap = True
        remaining = []
        for a, b in merged:
            if right <= a or left >= b:
                remaining.append((a, b))
            else:
                if a < left:
                    remaining.append((a, left))
                if right < b:
                    remaining.append((right, b))
        merged = remaining
    observed = sum((b - a).total_seconds() for a, b in merged)
    fraction = min(1.0, max(0.0, observed / duration)) if duration > 0 else 0.0
    if history_start is None or start < utc(history_start):
        quality = "insufficient_history"
    elif fraction >= 1 - 1e-9 and not known_gap:
        quality = "complete_observed_window"
    else:
        quality = "partial_coverage"
    return WindowCoverage(observed / 60, fraction, quality)
