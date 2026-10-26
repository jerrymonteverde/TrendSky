from datetime import UTC
from urllib.parse import parse_qs, urlsplit

import pytest
from trendsky_api.ingestion.protocol import (
    FrameError,
    JetstreamEvent,
    build_subscription_url,
    parse_frame,
)


def test_builds_v2_subscription_with_filtered_collections_and_inclusive_cursor():
    url = build_subscription_url("wss://example.test", 123456)
    parsed = urlsplit(url)
    assert parsed.path == "/xrpc/network.bsky.jetstream.subscribeEvents"
    assert parse_qs(parsed.query) == {
        "collections": ["app.bsky.feed.post"],
        "kinds": ["commit", "account", "sync"],
        "cursor": ["123456"],
    }


@pytest.mark.parametrize("path", ["", "/subscribe", "/xrpc/network.bsky.jetstream.subscribeEvents"])
def test_legacy_path_cannot_be_concatenated_with_v2_endpoint(path):
    result = urlsplit(build_subscription_url("wss://example.test" + path, 123))
    assert result.path == "/xrpc/network.bsky.jetstream.subscribeEvents"
    assert parse_qs(result.query)["cursor"] == ["123"]


def test_rejects_ambiguous_subscription_prefix():
    with pytest.raises(ValueError, match="canonical"):
        build_subscription_url(
            "wss://example.test/subscribe/xrpc/network.bsky.jetstream.subscribeEvents", 123
        )


def test_parses_v2_commit_envelope_and_timestamp_to_utc():
    parsed = parse_frame(
        '{"$type":"message","payload":{"$type":"#commit","seq":12,"time":"2026-10-24T12:00:00Z","did":"did:plc:abcdefghijklmnopqrstuvwx","operation":"create","collection":"app.bsky.feed.post","rkey":"abc","record":{"text":"hello"}}}'
    )
    assert isinstance(parsed, JetstreamEvent)
    assert parsed.seq == 12
    assert parsed.event_at.tzinfo == UTC
    assert parsed.operation == "create"
    assert parsed.record == {"text": "hello"}


@pytest.mark.parametrize("bad", ["{}", "not json", '{"$type":"message","payload":{}}'])
def test_rejects_invalid_and_unsupported_frames(bad):
    with pytest.raises(FrameError):
        parse_frame(bad)


def test_rejects_legacy_bare_jetstream_messages():
    with pytest.raises(FrameError, match="invalid_envelope"):
        parse_frame('{"kind":"commit","seq":1}')
