#!/usr/bin/env python3
"""
Source health monitoring for news-digest pipeline.

Tracks per-source success/failure history across current pipeline outputs and
prints a concise health report.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

HEALTH_FILE = Path("/tmp/news-digest-source-health.json")
DEFAULT_INPUT_DIR = Path("/tmp/news-digest")
HISTORY_DAYS = 7
FAILURE_THRESHOLD = 0.5
REPORT_LIMIT = 20

DEFAULT_INPUT_FILES = {
    "rss": "rss.json",
    "twitter": "twitter.json",
    "github": "github.json",
    "reddit": "reddit.json",
    "google": "google.json",
    "api": "api.json",
    "v2ex": "v2ex.json",
    "trending": "trending.json",
}


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")
    return logging.getLogger(__name__)


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_health_data(health_file: Path) -> Dict[str, Any]:
    data = load_json(health_file)
    return data if isinstance(data, dict) else {}


def save_health_data(health_file: Path, data: Dict[str, Any]) -> None:
    health_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def infer_input_path(input_dir: Optional[Path], explicit_path: Optional[Path], key: str) -> Optional[Path]:
    if explicit_path:
        return explicit_path
    if input_dir:
        return input_dir / DEFAULT_INPUT_FILES[key]
    return None


def normalize_source_records(payload: Dict[str, Any], source_type: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    if "sources" in payload and isinstance(payload["sources"], list):
        for source in payload["sources"]:
            sid = source.get("source_id", source.get("id", "unknown"))
            records.append(
                {
                    "source_id": sid,
                    "name": source.get("name", sid),
                    "source_type": source_type,
                    "status": source.get("status", "error"),
                }
            )
        return records

    if "subreddits" in payload and isinstance(payload["subreddits"], list):
        for subreddit in payload["subreddits"]:
            sid = subreddit.get("source_id", subreddit.get("id", "unknown"))
            records.append(
                {
                    "source_id": sid,
                    "name": subreddit.get("name", sid),
                    "source_type": source_type,
                    "status": subreddit.get("status", "error"),
                }
            )
        return records

    if "topics" in payload and isinstance(payload["topics"], list):
        for topic in payload["topics"]:
            topic_id = topic.get("topic_id", "unknown")
            records.append(
                {
                    "source_id": f"{source_type}-{topic_id}",
                    "name": f"{source_type}: {topic_id}",
                    "source_type": source_type,
                    "status": topic.get("status", "error"),
                }
            )
        return records

    if "repos" in payload and isinstance(payload["repos"], list):
        status = "ok" if payload.get("total", len(payload["repos"])) > 0 else "error"
        records.append(
            {
                "source_id": "github-trending",
                "name": "GitHub Trending",
                "source_type": source_type,
                "status": status,
            }
        )

    return records


def load_records_from_path(path: Optional[Path], source_type: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    if not path:
        return []
    payload = load_json(path)
    if payload is None:
        logger.debug(f"skip missing or invalid file: {path}")
        return []
    records = normalize_source_records(payload, source_type)
    logger.debug(f"loaded {len(records)} {source_type} health records from {path}")
    return records


def update_health(health: Dict[str, Any], records: Iterable[Dict[str, Any]], now: float) -> int:
    cutoff = now - HISTORY_DAYS * 86400
    updated = 0
    for record in records:
        sid = record["source_id"]
        if sid not in health:
            health[sid] = {
                "name": record["name"],
                "source_type": record.get("source_type", "unknown"),
                "checks": [],
            }
        health[sid]["name"] = record["name"]
        health[sid]["source_type"] = record.get("source_type", health[sid].get("source_type", "unknown"))
        health[sid]["checks"] = [check for check in health[sid]["checks"] if check["ts"] > cutoff]
        health[sid]["checks"].append({"ts": now, "ok": record.get("status") == "ok"})
        updated += 1
    return updated


def build_report_rows(health: Dict[str, Any], now: float) -> List[Dict[str, Any]]:
    cutoff = now - HISTORY_DAYS * 86400
    rows: List[Dict[str, Any]] = []
    for sid, info in health.items():
        checks = [check for check in info.get("checks", []) if check["ts"] > cutoff]
        if not checks:
            continue
        failures = sum(1 for check in checks if not check["ok"])
        success = len(checks) - failures
        failure_rate = failures / len(checks)
        rows.append(
            {
                "source_id": sid,
                "name": info.get("name", sid),
                "source_type": info.get("source_type", "unknown"),
                "checks": len(checks),
                "successes": success,
                "failures": failures,
                "failure_rate": failure_rate,
                "unhealthy": len(checks) >= 2 and failure_rate > FAILURE_THRESHOLD,
            }
        )
    rows.sort(key=lambda row: (-row["failure_rate"], -row["failures"], row["name"]))
    return rows


def print_report(rows: List[Dict[str, Any]], logger: logging.Logger) -> int:
    unhealthy_rows = [row for row in rows if row["unhealthy"]]
    logger.info(
        f"Health report: {len(rows)} tracked, {len(unhealthy_rows)} unhealthy, "
        f"{sum(row['checks'] for row in rows)} checks in last {HISTORY_DAYS} days"
    )
    for row in rows[:REPORT_LIMIT]:
        if row["unhealthy"]:
            icon = "⚠️"
        elif row["failures"] > 0:
            icon = "🟡"
        else:
            icon = "✅"
        logger.info(
            f"{icon} [{row['source_type']}] {row['name']} "
            f"- {row['successes']}/{row['checks']} ok ({row['failure_rate']:.0%} failure)"
        )
    return len(unhealthy_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track source health for news-digest pipeline.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory containing current run JSON outputs")
    parser.add_argument("--health-file", type=Path, default=HEALTH_FILE, help="Persisted source health JSON path")
    parser.add_argument("--rss", type=Path, help="RSS output JSON")
    parser.add_argument("--twitter", type=Path, help="Twitter output JSON")
    parser.add_argument("--github", type=Path, help="GitHub output JSON")
    parser.add_argument("--reddit", type=Path, help="Reddit output JSON")
    parser.add_argument("--google", type=Path, help="Google output JSON")
    parser.add_argument("--api", type=Path, help="API output JSON")
    parser.add_argument("--v2ex", type=Path, help="V2EX output JSON")
    parser.add_argument("--trending", type=Path, help="GitHub trending output JSON")
    parser.add_argument("--report-only", action="store_true", help="Only print current health report without updating history")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logging(args.verbose)
    now = time.time()
    health = load_health_data(args.health_file)

    if not args.report_only:
        updated_total = 0
        for key in DEFAULT_INPUT_FILES:
            path = infer_input_path(args.input_dir, getattr(args, key), key)
            updated_total += update_health(
                health,
                load_records_from_path(path, key, logger),
                now,
            )
        save_health_data(args.health_file, health)
        logger.info(f"Updated source health from {updated_total} records")

    rows = build_report_rows(health, now)
    unhealthy = print_report(rows, logger)
    return 0 if rows or args.report_only else 0


if __name__ == "__main__":
    sys.exit(main())
