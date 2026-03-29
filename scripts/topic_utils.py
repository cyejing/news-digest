#!/usr/bin/env python3
"""Utilities for normalizing and resolving single-topic assignments."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ENV_DEFAULTS_DIR = "NEWS_HOTSPOTS_DEFAULTS_DIR"
ENV_CONFIG_DIR = "NEWS_HOTSPOTS_CONFIG_DIR"
DEFAULT_DEFAULTS_DIR = Path(__file__).resolve().parent.parent / "config" / "defaults"
DEFAULT_TOPIC_RULES_FILENAME = "topic-rules.json"
OVERLAY_TOPIC_RULES_FILENAME = "news-hotspots-topic-rules.json"


def _deep_merge_dicts(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_json_file(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


@lru_cache(maxsize=8)
def load_default_topic_rules(
    defaults_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> Dict[str, Any]:
    effective_defaults_dir = Path(
        defaults_dir or os.environ.get(ENV_DEFAULTS_DIR) or DEFAULT_DEFAULTS_DIR
    )
    effective_config_dir = config_dir or os.environ.get(ENV_CONFIG_DIR)

    rules = _load_json_file(effective_defaults_dir / DEFAULT_TOPIC_RULES_FILENAME)
    if effective_config_dir:
        overlay_rules = _load_json_file(Path(effective_config_dir) / OVERLAY_TOPIC_RULES_FILENAME)
        if overlay_rules:
            rules = _deep_merge_dicts(rules, overlay_rules)
    return rules


def get_legacy_topic_map(rules: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    effective_rules = rules or load_default_topic_rules()
    legacy_map = effective_rules.get("legacy_topic_map")
    if isinstance(legacy_map, dict):
        return {
            str(key).strip(): str(value).strip()
            for key, value in legacy_map.items()
            if str(key).strip() and str(value).strip()
        }
    return {}


def get_topic_priority_list(rules: Optional[Dict[str, Any]] = None) -> List[str]:
    effective_rules = rules or load_default_topic_rules()
    topic_priority = effective_rules.get("topic_priority")
    if isinstance(topic_priority, list):
        normalized = [str(item).strip() for item in topic_priority if str(item).strip()]
        if normalized:
            return normalized
    return []


def normalize_topic_id(value: Any, rules: Optional[Dict[str, Any]] = None) -> str:
    """Normalize a topic id and map legacy ids into the current taxonomy."""
    if value is None:
        return ""
    topic_id = str(value).strip()
    if not topic_id:
        return ""
    return get_legacy_topic_map(rules).get(topic_id, topic_id)


def topic_priority(topic_id: Any, rules: Optional[Dict[str, Any]] = None) -> int:
    normalized = normalize_topic_id(topic_id, rules=rules)
    topic_priority_list = get_topic_priority_list(rules)
    topic_priority_index = {item: index for index, item in enumerate(topic_priority_list)}
    return topic_priority_index.get(normalized, len(topic_priority_list))


def _iter_topic_candidates(value: Any, rules: Optional[Dict[str, Any]] = None) -> Iterable[str]:
    if isinstance(value, dict):
        topic = normalize_topic_id(value.get("topic"), rules=rules)
        if topic:
            yield topic
        raw_topics = value.get("topics")
        if isinstance(raw_topics, list):
            for item in raw_topics:
                topic = normalize_topic_id(item, rules=rules)
                if topic:
                    yield topic
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_topic_candidates(item, rules=rules)
        return

    topic = normalize_topic_id(value, rules=rules)
    if topic:
        yield topic


def resolve_primary_topic(value: Any, default: str = "", rules: Optional[Dict[str, Any]] = None) -> str:
    """Resolve a single primary topic from a topic value, list, or record."""
    candidates: List[str] = []
    seen = set()
    for topic_id in _iter_topic_candidates(value, rules=rules):
        if topic_id not in seen:
            seen.add(topic_id)
            candidates.append(topic_id)
    if not candidates:
        return normalize_topic_id(default, rules=rules)
    return min(candidates, key=lambda topic_id: topic_priority(topic_id, rules=rules))


def get_source_topic(source: Dict[str, Any], default: str = "", rules: Optional[Dict[str, Any]] = None) -> str:
    """Return the normalized single topic for a source config or output record."""
    return resolve_primary_topic(source, default=default, rules=rules)
