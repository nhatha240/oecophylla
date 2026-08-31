"""Canonical recommendation behavior label derivation.

This module is intentionally dependency-free so the offline pipeline, online
evaluator, and feature worker can ship the exact same semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Mapping

LabelVersion = Literal["v1", "v2"]
Semantic = Literal[
    "exposure",
    "click",
    "qualified_read",
    "positive",
    "strong_positive",
    "negative",
    "strong_negative",
]

QUALIFIED_READ_MS = 10_000
CONTRACT_VERSION = "engagement-label-v2"
PRECEDENCE: tuple[Semantic, ...] = (
    "strong_negative",
    "strong_positive",
    "positive",
    "qualified_read",
    "click",
    "negative",
    "exposure",
)
REVERSALS = {
    "unlike": "like",
    "unsave": "save",
    "unshare": "share",
    "unhide": "hide",
}


@dataclass(frozen=True)
class LabelResult:
    semantic: Semantic
    training_target: int | None
    accepted_events: int
    deduplicated_events: int
    reversed_event_types: tuple[str, ...] = ()
    processing_order: tuple[str, ...] = ()


def _value(event: Any, name: str, default: Any = None) -> Any:
    if isinstance(event, Mapping):
        if name in event:
            return event[name]
        metadata = event.get("metadata")
        if isinstance(metadata, Mapping) and name in metadata:
            return metadata[name]
        return default
    value = getattr(event, name, default)
    if value is not None:
        return value
    metadata = getattr(event, "metadata", None)
    return metadata.get(name, default) if isinstance(metadata, Mapping) else default


def _event_mapping(event: Any, defaults: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(event, Mapping):
        return {**defaults, **event}
    values = dict(defaults)
    for name in (
        "id",
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "ingested_at",
        "dwell_ms",
        "continuous_visible_ms",
        "metadata",
    ):
        value = getattr(event, name, None)
        if value is not None:
            values["event_id" if name == "id" else name] = value
    return values


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_payload(event: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), repr(value)) for key, value in event.items()))


def derive_label(
    events: Iterable[Any],
    *,
    label_version: LabelVersion,
    qualified_read_ms: int = QUALIFIED_READ_MS,
    label_window_closed: bool = True,
    defaults: Mapping[str, Any] | None = None,
) -> LabelResult:
    if label_version not in ("v1", "v2"):
        raise ValueError("label_version must be v1 or v2")
    if qualified_read_ms <= 0:
        raise ValueError("qualified_read_ms must be positive")

    expanded = [_event_mapping(event, defaults or {}) for event in events]
    unique: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    duplicates = 0
    for event in expanded:
        event_id = event.get("event_id")
        if event_id is None:
            anonymous.append(event)
            continue
        key = str(event_id)
        existing = unique.get(key)
        if existing is None:
            unique[key] = event
        elif _canonical_payload(existing) == _canonical_payload(event):
            duplicates += 1
        else:
            raise ValueError(f"conflicting duplicate event: {key}")

    accepted = [*unique.values(), *anonymous]
    accepted.sort(
        key=lambda event: (
            _timestamp(event.get("occurred_at")),
            _timestamp(event.get("ingested_at")),
            str(event.get("event_id", "")),
        )
    )
    active = {"like": False, "save": False, "share": False, "hide": False}
    irreversible: set[Semantic] = set()
    visible = False
    reversed_types: list[str] = []

    for event in accepted:
        event_type = str(event.get("event_type", ""))
        if event_type in active:
            active[event_type] = True
        elif event_type in REVERSALS:
            reversed_type = REVERSALS[event_type]
            active[reversed_type] = False
            if reversed_type not in reversed_types:
                reversed_types.append(reversed_type)
        elif event_type == "visible":
            visible = True
        elif event_type == "click":
            irreversible.add("click")
        elif event_type == "comment":
            irreversible.add("positive")
        elif event_type == "report":
            irreversible.add("strong_negative")

        duration = _value(event, "continuous_visible_ms")
        if duration is None:
            duration = _value(event, "dwell_ms")
        if (
            event_type in {"view", "dwell"}
            and duration is not None
            and int(duration) >= qualified_read_ms
        ):
            irreversible.add("qualified_read" if label_version == "v2" else "positive")

    candidates: set[Semantic] = set(irreversible)
    if active["hide"]:
        candidates.add("strong_negative")
    if active["save"] or active["share"]:
        candidates.add("strong_positive")
    if active["like"]:
        candidates.add("positive")
    if label_version == "v1" and "click" in candidates:
        candidates.remove("click")
        candidates.add("positive")
    if visible:
        candidates.add("negative" if label_window_closed else "exposure")
    elif not candidates:
        candidates.add("negative" if label_window_closed else "exposure")

    semantic = next(item for item in PRECEDENCE if item in candidates)
    target = None if semantic == "exposure" else int(
        semantic in {"click", "qualified_read", "positive", "strong_positive"}
    )
    return LabelResult(
        semantic=semantic,
        training_target=target,
        accepted_events=len(accepted),
        deduplicated_events=duplicates,
        reversed_event_types=tuple(reversed_types),
        processing_order=tuple(str(event.get("event_id", "")) for event in accepted),
    )


__all__ = [
    "CONTRACT_VERSION",
    "LabelResult",
    "LabelVersion",
    "PRECEDENCE",
    "QUALIFIED_READ_MS",
    "derive_label",
]
