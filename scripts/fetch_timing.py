#!/usr/bin/env python3
"""Shared helpers for request timing traces in fetch scripts."""

from typing import Any, Dict, Iterable, List

SLOW_REQUEST_THRESHOLDS = (3.0, 5.0, 10.0)


def timing_keywords(elapsed_s: float) -> List[str]:
    keywords = ["timed_request"]
    for threshold in SLOW_REQUEST_THRESHOLDS:
        if elapsed_s >= threshold:
            threshold_label = str(int(threshold)) if float(threshold).is_integer() else str(threshold).replace(".", "_")
            keywords.append(f"slow_ge_{threshold_label}s")
    return keywords


def build_request_trace(target: str, elapsed_s: float, status: str = "ok", **extra: Any) -> Dict[str, Any]:
    trace = {
        "target": target,
        "status": status,
        "elapsed_s": round(float(elapsed_s), 3),
        "timing_keywords": timing_keywords(float(elapsed_s)),
    }
    trace.update(extra)
    return trace


def summarize_request_traces(traces: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        "requests_total": 0,
        "requests_ok": 0,
        "requests_error": 0,
        "slow_requests_ge_3s": 0,
        "slow_requests_ge_5s": 0,
        "slow_requests_ge_10s": 0,
    }
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        summary["requests_total"] += 1
        if trace.get("status") == "ok":
            summary["requests_ok"] += 1
        else:
            summary["requests_error"] += 1
        keywords = trace.get("timing_keywords", [])
        if "slow_ge_3s" in keywords:
            summary["slow_requests_ge_3s"] += 1
        if "slow_ge_5s" in keywords:
            summary["slow_requests_ge_5s"] += 1
        if "slow_ge_10s" in keywords:
            summary["slow_requests_ge_10s"] += 1
    return summary
