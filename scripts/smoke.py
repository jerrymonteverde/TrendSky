"""Verify a running TrendSky stack and its read-only ingestion status endpoints."""

import argparse
import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


def verify(api_url: str, web_url: str) -> None:
    with urlopen(f"{api_url}/api/v1/health", timeout=10) as response:
        health = json.load(response)
        if health.get("database") != "connected" or health.get("schema_status") != "ready":
            raise ValueError("Database or migration readiness did not pass.")
    with urlopen(f"{api_url}/api/v1/analytics/summary", timeout=10) as response:
        summary = json.load(response)
        if summary.get("collection_status") not in {
            "not_started",
            "connecting",
            "collecting",
            "reconnecting",
            "interrupted",
            "error",
        }:
            raise ValueError("Unexpected collection status.")
    with urlopen(f"{api_url}/api/v1/ingestion/status", timeout=10) as response:
        status = json.load(response)
        if status.get("source") != "bluesky" or not isinstance(status.get("posts_stored"), int):
            raise ValueError("Ingestion status contract did not pass.")
    with urlopen(f"{api_url}/api/v1/ingestion/stats", timeout=10) as response:
        if not isinstance(json.load(response).get("total_events_received"), int):
            raise ValueError("Ingestion statistics contract did not pass.")
    with urlopen(f"{api_url}/api/v1/trending/status", timeout=10) as response:
        if json.load(response).get("algorithm_version") != "deterministic-v1":
            raise ValueError("Trend processor status contract did not pass.")
    with urlopen(f"{api_url}/api/v1/trending?window=5&category=popular", timeout=10) as response:
        if not isinstance(json.load(response).get("items"), list):
            raise ValueError("Persisted trending response contract did not pass.")
    for route in ["/", "/explore?q=%23ciencia", "/trending", "/predictions", "/about"]:
        with urlopen(f"{web_url}{route}", timeout=15) as response:
            if response.status != 200 or "TrendSky" not in response.read().decode():
                raise ValueError(f"Web route check failed: {route}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--web-url", default="http://localhost:3000")
    args = parser.parse_args()
    try:
        verify(args.api_url.rstrip("/"), args.web_url.rstrip("/"))
    except (URLError, ValueError, TimeoutError):
        print(
            "Foundation smoke checks failed. Check service health and migration logs.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("TrendSky HTTP, database readiness, ingestion/trending status and route checks passed.")
