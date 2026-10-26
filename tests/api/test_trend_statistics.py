from datetime import UTC, datetime, timedelta

import pytest
from trendsky_api.config import Settings
from trendsky_api.trends.coverage import WindowCoverage, window_coverage
from trendsky_api.trends.statistics import Activity, calculate

COMPLETE = WindowCoverage(5, 1, "complete_observed_window")
PARTIAL = WindowCoverage(2.5, 0.5, "partial_coverage")


def metrics(c, p, *, u=10, coverage=None, baseline=None):
    return calculate(
        Activity(c, min(u, c), min(c, u * 3)),
        Activity(p, min(10, p), p),
        [Activity(value, value, value) for value in (baseline or [12] * 6)],
        coverage or [COMPLETE] * 8,
        5,
        Settings(_env_file=None),
    )


@pytest.mark.parametrize(
    "c,p,growth,status",
    [
        (20, 8, 150, "Rising"),
        (12, 12, 0, "Stable"),
        (4, 12, -100 * 8 / 12, "Declining"),
        (0, 12, -100, "Declining"),
        (25, 20, 25, "Rising"),
        (15, 20, -25, "Declining"),
    ],
)
def test_traceable_growth_and_thresholds(c, p, growth, status):
    value = metrics(c, p, baseline=[20] * 6)
    assert value["growth_percent"] == pytest.approx(growth, abs=0.0001)
    assert value["trend_status"] == status
    assert value["acceleration"] == pytest.approx((c - p) / 25)
    assert value["velocity"] == c / 5


def test_zero_previous_is_new_activity_with_no_infinite_percentage():
    result = metrics(10, 0, baseline=[0] * 6)
    assert result["growth_percent"] is None
    assert result["growth_state"] == "new_activity"
    assert result["trend_status"] == "Emerging"
    assert result["baseline_deviation"] is None
    assert result["baseline_state"] == "zero_variance"


def test_partial_coverage_never_becomes_apparent_growth_or_decline():
    for c, p in [(10, 5), (0, 20)]:
        value = metrics(c, p, coverage=[PARTIAL, COMPLETE] + [COMPLETE] * 6)
        assert value["growth_percent"] is None
        assert value["acceleration"] is None
        assert value["trend_status"] == "Insufficient Data"
        assert value["rising_score"] is None
        assert value["velocity"] == c / 2.5


def test_single_author_cannot_qualify_or_dominate_by_repetition():
    value = metrics(1000, 1, u=1)
    assert value["popular_score"] == 0
    assert value["rising_score"] is None
    assert value["trend_status"] == "Insufficient Data"
    assert 0 <= value["momentum_score"] <= 100


def test_robust_baseline_uses_only_complete_windows_and_handles_outlier():
    value = metrics(20, 12, baseline=[10, 11, 12, 13, 14, 1000])
    assert value["baseline_median"] == 12.5
    assert value["baseline_mad"] == 1.5
    assert value["baseline_deviation"] == pytest.approx(7.5 / (1.4826 * 1.5))
    assert metrics(20, 12, coverage=[COMPLETE] * 2 + [PARTIAL] * 6)["baseline_median"] is None


def test_coverage_merges_sessions_and_subtracts_gaps():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(minutes=5)
    assert window_coverage(start, end, [(start, end)], [], start).complete
    gap = (start + timedelta(minutes=2), start + timedelta(minutes=3))
    value = window_coverage(start, end, [(start, end), (start, end)], [gap], start)
    assert value.fraction == 0.8
    assert value.observed_minutes == 4
    assert not value.complete
    assert window_coverage(start, end, [], [], None).quality == "insufficient_history"
    assert (
        window_coverage(start, end, [(start, end)], [], start + timedelta(seconds=1)).quality
        == "insufficient_history"
    )
