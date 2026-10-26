"""Read-only sustained API observation. Never changes checkpoints or restarts workers."""

import argparse
import json
import time
from urllib.error import URLError
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://localhost:8000")
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--require-trends", action="store_true")
    args = parser.parse_args()
    if args.seconds < 60 or not 1 <= args.interval <= 60:
        parser.error("Observe at least 60 seconds; interval must be 1–60 seconds.")
    samples = []
    errors = 0
    trends_ok = False
    deadline = time.monotonic() + args.seconds
    while True:
        try:

            def get(path):
                with urlopen(args.origin.rstrip("/") + "/api/v1/" + path, timeout=5) as response:
                    return json.load(response)

            ingestion = get("ingestion/status")
            stats = get("ingestion/stats")
            trends = get("trending/status")
            sample = {
                key: ingestion.get(key)
                for key in (
                    "status",
                    "health",
                    "worker_fresh",
                    "posts_stored",
                    "last_seq",
                    "last_persisted_at",
                    "event_lag_seconds",
                    "cursor_expired",
                )
            }
            sample.update(
                {
                    "processing_errors": stats.get("processing_errors"),
                    "reconnection_count": stats.get("reconnection_count"),
                    "trend_health": trends.get("health"),
                    "backlog": trends.get("backlog"),
                }
            )
            samples.append(sample)
            if args.require_trends:
                page = get("trending?window=5&limit=3")
                trends_ok = (
                    bool(page.get("items"))
                    and trends.get("worker_fresh")
                    and trends.get("health") in {"up_to_date", "processing_backlog"}
                )
            print(json.dumps(sample), flush=True)
        except (URLError, TimeoutError, ValueError, KeyError):
            errors += 1
            print(json.dumps({"sample_unavailable": True}), flush=True)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(args.interval, remaining))
    first, last = (samples[0], samples[-1]) if samples else ({}, {})
    healthy = bool(samples) and all(
        sample.get("health") == "connected"
        and sample.get("worker_fresh")
        and not sample.get("cursor_expired")
        for sample in samples
    )
    advanced = bool(samples) and (last.get("last_seq") or 0) > (first.get("last_seq") or 0)
    increased = bool(samples) and last.get("posts_stored", 0) > first.get("posts_stored", 0)
    no_failures = bool(samples) and (
        first.get("processing_errors") == last.get("processing_errors")
        and first.get("reconnection_count") == last.get("reconnection_count")
    )
    passed = (
        not errors
        and healthy
        and advanced
        and increased
        and no_failures
        and (not args.require_trends or trends_ok)
    )
    print(
        json.dumps(
            {
                "verified": passed,
                "samples": len(samples),
                "unavailable": errors,
                "checkpoint_advanced": advanced,
                "retained_posts_increased": increased,
                "no_new_errors_or_reconnections": no_failures,
                "trend_results_verified": trends_ok if args.require_trends else None,
            }
        )
    )
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
