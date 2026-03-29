#!/usr/bin/env python3
"""Utilities for normalizing and resolving single-topic assignments."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

LEGACY_TOPIC_MAP = {
    "ai-models": "ai-frontier",
    "ai-agents": "ai-frontier",
    "ai-ecosystem": "ai-infra",
    "developer-tools": "technology",
    "markets-business": "business",
    "macro-policy": "business",
    "world-affairs": "world",
    "cybersecurity": "technology",
}

TOPIC_PRIORITY = [
    "github",
    "ai-infra",
    "ai-frontier",
    "technology",
    "business",
    "world",
    "science",
    "social",
]

_TOPIC_PRIORITY_INDEX = {topic_id: index for index, topic_id in enumerate(TOPIC_PRIORITY)}


def normalize_topic_id(value: Any) -> str:
    """Normalize a topic id and map legacy ids into the current taxonomy."""
    if value is None:
        return ""
    topic_id = str(value).strip()
    if not topic_id:
        return ""
    return LEGACY_TOPIC_MAP.get(topic_id, topic_id)


def topic_priority(topic_id: Any) -> int:
    normalized = normalize_topic_id(topic_id)
    return _TOPIC_PRIORITY_INDEX.get(normalized, len(TOPIC_PRIORITY))


def _iter_topic_candidates(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        topic = normalize_topic_id(value.get("topic"))
        if topic:
            yield topic
        raw_topics = value.get("topics")
        if isinstance(raw_topics, list):
            for item in raw_topics:
                topic = normalize_topic_id(item)
                if topic:
                    yield topic
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            topic = normalize_topic_id(item)
            if topic:
                yield topic
        return

    topic = normalize_topic_id(value)
    if topic:
        yield topic


def resolve_primary_topic(value: Any, default: str = "") -> str:
    """Resolve a single primary topic from a topic value, list, or record."""
    candidates: List[str] = []
    seen = set()
    for topic_id in _iter_topic_candidates(value):
        if topic_id not in seen:
            seen.add(topic_id)
            candidates.append(topic_id)
    if not candidates:
        return normalize_topic_id(default)
    return min(candidates, key=topic_priority)


def get_source_topic(source: Dict[str, Any], default: str = "") -> str:
    """Return the normalized single topic for a source config or output record."""
    return resolve_primary_topic(source, default=default)

