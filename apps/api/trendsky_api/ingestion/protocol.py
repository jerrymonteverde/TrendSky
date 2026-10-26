"""Strict parser and URL builder for the Jetstream v2 JSON WebSocket protocol."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

COLLECTION = "app.bsky.feed.post"
KINDS = ("commit", "account", "sync")
_HASHTAG = re.compile(r"(?<![\w])#([\w]{1,127})", re.UNICODE)
_DID = re.compile(r"^did:(?:plc:[a-z2-7]{24}|web:.+)$")


@dataclass(frozen=True, slots=True)
class JetstreamEvent:
    seq: int
    event_at: datetime
    kind: str
    did: str | None = None
    operation: str | None = None
    rkey: str | None = None
    record: dict[str, Any] | None = None
    account_active: bool | None = None
    account_status: str | None = None


@dataclass(frozen=True, slots=True)
class JetstreamInfo:
    name: str
    message: str


class FrameError(ValueError):
    """Invalid or unsupported v2 frame; sequence is retained when safely available."""

    def __init__(self, reason: str, seq: int | None = None) -> None:
        super().__init__(reason)
        self.seq = seq


def build_subscription_url(base_url: str, cursor: int | None) -> str:
    """Build a v2 URL with repeated collection/kind filters and optional inclusive cursor."""
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"wss", "ws"} or not parsed.hostname or parsed.username:
        raise ValueError("JETSTREAM_URL must be a WebSocket URL without credentials.")
    endpoint = "/xrpc/network.bsky.jetstream.subscribeEvents"
    path = parsed.path.rstrip("/")
    if path not in {"", "/subscribe", endpoint}:
        raise ValueError("JETSTREAM_URL must use the canonical Jetstream v2 subscription path.")
    path = endpoint
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query)
        if key not in {"collections", "kinds", "cursor"}
    ]
    query.extend(("collections", value) for value in (COLLECTION,))
    query.extend(("kinds", value) for value in KINDS)
    if cursor is not None:
        query.append(("cursor", str(cursor)))
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query), ""))


def _sequence(payload: dict[str, Any]) -> int | None:
    value = payload.get("seq")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("event timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("event timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("event timestamp must include a timezone")
    return parsed.astimezone(UTC)


def parse_frame(frame: str | bytes) -> JetstreamEvent | JetstreamInfo:
    """Decode the v2 `message` envelope and validate its typed payload."""
    try:
        envelope = json.loads(frame)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise FrameError("invalid_json") from exc
    if not isinstance(envelope, dict) or envelope.get("$type") != "message":
        raise FrameError("invalid_envelope")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise FrameError("missing_payload")
    seq = _sequence(payload)
    raw_type = payload.get("$type")
    if not isinstance(raw_type, str) or "#" not in raw_type:
        raise FrameError("missing_event_type", seq)
    kind = raw_type.rsplit("#", 1)[-1]
    if kind == "info":
        info = payload.get("info")
        if not isinstance(info, dict):
            raise FrameError("invalid_info_payload")
        name = info.get("name")
        message = info.get("message", "")
        if not isinstance(name, str):
            raise FrameError("invalid_info_name")
        return JetstreamInfo(name[:80], message[:160] if isinstance(message, str) else "")
    if seq is None:
        raise FrameError("invalid_sequence")
    try:
        event_at = _timestamp(payload.get("time"))
    except ValueError as exc:
        raise FrameError("invalid_timestamp", seq) from exc

    if kind == "commit":
        did, operation, rkey = payload.get("did"), payload.get("operation"), payload.get("rkey")
        if not isinstance(did, str) or not _DID.fullmatch(did):
            raise FrameError("invalid_did", seq)
        if payload.get("collection") != COLLECTION:
            raise FrameError("unexpected_collection", seq)
        if operation not in {"create", "update", "delete"}:
            raise FrameError("invalid_operation", seq)
        if not isinstance(rkey, str) or not rkey or len(rkey) > 128:
            raise FrameError("invalid_record_key", seq)
        record = payload.get("record")
        if operation != "delete" and not isinstance(record, dict):
            raise FrameError("missing_record", seq)
        return JetstreamEvent(
            seq=seq,
            event_at=event_at,
            kind=kind,
            did=did,
            operation=operation,
            rkey=rkey,
            record=record if isinstance(record, dict) else None,
        )

    if kind in {"account", "sync"}:
        did = payload.get("did")
        nested = payload.get(kind)
        if not isinstance(nested, dict):
            raise FrameError(f"missing_{kind}_payload", seq)
        nested_did = nested.get("did", did)
        if not isinstance(did, str) or not _DID.fullmatch(did):
            raise FrameError("invalid_did", seq)
        if nested_did != did:
            raise FrameError("marker_did_mismatch", seq)
        active = nested.get("active")
        status = nested.get("status")
        return JetstreamEvent(
            seq=seq,
            event_at=event_at,
            kind=kind,
            did=did,
            account_active=active if isinstance(active, bool) else None,
            account_status=status if isinstance(status, str) else None,
        )

    raise FrameError("unsupported_event_kind", seq)


def hashtags_from_record(record: dict[str, Any]) -> set[str]:
    """Extract normalized hashtags from text and explicit AT rich-text tag facets."""
    tags: set[str] = set()
    text = record.get("text")
    if isinstance(text, str):
        tags.update(match.group(1).casefold() for match in _HASHTAG.finditer(text))
    facets = record.get("facets")
    if isinstance(facets, list):
        for facet in facets:
            if not isinstance(facet, dict) or not isinstance(facet.get("features"), list):
                continue
            for feature in facet["features"]:
                if (
                    isinstance(feature, dict)
                    and feature.get("$type") == "app.bsky.richtext.facet#tag"
                    and isinstance(feature.get("tag"), str)
                ):
                    tag = feature["tag"].removeprefix("#").casefold()
                    if tag and len(tag) <= 128 and not any(char.isspace() for char in tag):
                        tags.add(tag)
    return tags
