"""Bounded descriptive signals; robust deviation is not a significance test."""

import math
from dataclasses import dataclass
from statistics import median
from typing import Any

from trendsky_api.config import Settings
from trendsky_api.trends.coverage import WindowCoverage


@dataclass(frozen=True)
class Activity:
    posts: int = 0
    contributors: int = 0
    capped_posts: int = 0


def calculate(
    current: Activity,
    previous: Activity,
    history: list[Activity],
    coverage: list[WindowCoverage],
    window: int,
    settings: Settings,
) -> dict[str, Any]:
    c, p, u = current.posts, previous.posts, current.contributors
    comparable = coverage[0].complete and coverage[1].complete
    growth = (c - p) / p * 100 if comparable and p > 0 else None
    growth_state = (
        ("comparable" if p > 0 else "new_activity" if c else "no_activity")
        if comparable
        else "insufficient_baseline"
    )
    velocity = c / coverage[0].observed_minutes if coverage[0].observed_minutes > 0 else None
    acceleration = (c - p) / (window * window) if comparable else None
    baseline = [
        sample.posts
        for sample, quality in zip(history, coverage[2:], strict=True)
        if quality.complete
    ]
    baseline_ok = len(baseline) >= settings.trends_min_baseline_windows
    center = float(median(baseline)) if baseline_ok else None
    mad = float(median([abs(value - center) for value in baseline])) if center is not None else None
    deviation = (c - center) / (1.4826 * mad) if center is not None and mad else None
    lift = (c + 1) / (center + 1) if center is not None else None
    enough = c >= settings.trends_min_posts and u >= settings.trends_min_contributors
    emerging_sample = (
        c >= settings.trends_emerging_min_posts and u >= settings.trends_emerging_min_contributors
    )
    rising = (
        comparable
        and current.capped_posts > previous.capped_posts
        and (
            (growth is not None and growth >= settings.trends_growth_threshold)
            or (p == 0 and emerging_sample)
        )
    )
    emerging = (
        rising
        and emerging_sample
        and (p == 0 or (lift is not None and lift >= settings.trends_emerging_lift))
    )
    status = "Insufficient Data"
    if enough and comparable:
        if emerging:
            status = "Emerging"
        elif rising:
            status = "Rising"
        elif growth is not None and growth <= -settings.trends_growth_threshold:
            status = "Declining"
        elif growth is not None and abs(growth) < settings.trends_growth_threshold:
            status = "Stable"
    elif (
        comparable
        and p >= settings.trends_min_posts
        and previous.contributors >= settings.trends_min_contributors
        and c < p
        and growth is not None
        and growth <= -settings.trends_growth_threshold
    ):
        # A formerly substantial conversation can decline to zero.
        status = "Declining"
    v = current.capped_posts / (current.capped_posts + 20)
    participation = u / (u + 10)
    g = (
        max(
            0.0,
            (current.capped_posts - previous.capped_posts)
            / (current.capped_posts + previous.capped_posts + 1),
        )
        if comparable
        else 0.0
    )
    b = max(0.0, (c - center) / (c + center + 1)) if center is not None else 0.0
    momentum = 100 * (0.25 * v + 0.25 * participation + 0.35 * g + 0.15 * b)
    popular = math.log1p(current.capped_posts) * math.log1p(u) if enough else 0.0
    return {
        "current_activity": c,
        "previous_activity": p if coverage[1].complete else None,
        "unique_contributors": u,
        "contributor_capped_activity": current.capped_posts,
        "growth_percent": round(growth, 4) if growth is not None else None,
        "growth_state": growth_state,
        "velocity": round(velocity, 6) if velocity is not None else None,
        "acceleration": round(acceleration, 8) if acceleration is not None else None,
        "momentum_score": round(momentum, 6),
        "trend_status": status,
        "coverage_status": coverage[0].quality,
        "coverage_fraction": coverage[0].fraction,
        "previous_coverage_fraction": coverage[1].fraction,
        "observed_minutes": coverage[0].observed_minutes,
        "comparison_valid": comparable,
        "baseline_windows": len(baseline),
        "baseline_median": center,
        "baseline_mad": mad,
        "baseline_deviation": deviation,
        "baseline_lift": lift,
        "baseline_state": "available"
        if mad
        else "zero_variance"
        if baseline_ok
        else "insufficient_history",
        "popular_score": round(popular, 8),
        "rising_score": round(momentum * g, 8) if enough and rising else None,
        "emerging_score": round(momentum * max(g, b), 8) if enough and emerging else None,
    }
