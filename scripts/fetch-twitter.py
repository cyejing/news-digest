#!/usr/bin/env python3
"""
Fetch Twitter/X timelines and topic-grouped search results via bb-browser.

Reads timeline sources from sources.json and topic queries from topics.json.
Both modes run sequentially in one step and share a single cooldown bucket.
"""

import argparse
import html
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from config_loader import load_merged_sources, load_merged_topics
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from config_loader import load_merged_sources, load_merged_topics

try:
    from topic_utils import get_source_topic
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from topic_utils import get_source_topic

COOLDOWN_SECONDS = float(os.environ.get("BB_BROWSER_TWITTER_COOLDOWN_SECONDS", "7.0"))
DEFAULT_TIMEOUT = 180
DEFAULT_COUNT = 20
DEFAULT_RESULTS_PER_QUERY = 5
MAX_COUNT = 100
MAX_RESULTS_PER_QUERY = 20
TWITTER_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"
_last_success_at: Optional[float] = None


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def throttle_after_success() -> None:
    global _last_success_at
    if _last_success_at is None:
        return
    wait_seconds = COOLDOWN_SECONDS - (time.monotonic() - _last_success_at)
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def run_bb_browser_site(args: Sequence[str], timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    global _last_success_at
    throttle_after_success()
    result = subprocess.run(
        ["bb-browser", "site", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "bb-browser command failed").strip()
        raise RuntimeError(message)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from bb-browser: {exc}") from exc

    _last_success_at = time.monotonic()
    return payload


def load_sources(defaults_dir: Path, config_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    all_sources = load_merged_sources(defaults_dir, config_dir)
    return [source for source in all_sources if source.get("type") == "twitter" and source.get("enabled", True)]


def normalize_text(text: str) -> str:
    return " ".join(html.unescape(text or "").split())


def truncate_text(text: str, limit: int = 280) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def parse_twitter_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, TWITTER_DATE_FORMAT).astimezone(timezone.utc)
    except ValueError:
        return None


def within_hours(tweet_dt: Optional[datetime], cutoff: datetime) -> bool:
    if tweet_dt is None:
        return False
    return tweet_dt >= cutoff


def timeline_count_for_source(source: Dict[str, Any]) -> int:
    try:
        count = int(source.get("limit", DEFAULT_COUNT))
    except (TypeError, ValueError):
        count = DEFAULT_COUNT
    return max(1, min(MAX_COUNT, count))


def result_count_for_topic(topic: Dict[str, Any]) -> int:
    display = topic.get("display", {})
    max_items = display.get("max_items", DEFAULT_RESULTS_PER_QUERY)
    try:
        return max(1, min(MAX_RESULTS_PER_QUERY, int(max_items)))
    except (TypeError, ValueError):
        return DEFAULT_RESULTS_PER_QUERY


def format_search_term(term: str, exclude: bool = False) -> str:
    value = normalize_text(term)
    if not value:
        return ""
    if " " in value:
        value = f"\"{value}\""
    return f"-{value}" if exclude else value


def build_twitter_query(base_query: str, exclude: List[str]) -> str:
    parts = [normalize_text(base_query)]
    parts.extend(
        formatted
        for formatted in (format_search_term(term, exclude=True) for term in exclude)
        if formatted
    )
    return " ".join(part for part in parts if part)


def extract_tweets(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    for key in ("tweets", "results", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            for nested_key in ("tweets", "results", "items"):
                nested_value = value.get(nested_key)
                if isinstance(nested_value, list):
                    return [item for item in nested_value if isinstance(item, dict)]
    return []


def parse_tweet(item: Dict[str, Any], topic_id: str, cutoff: datetime, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
    text = truncate_text(item.get("text", item.get("full_text", "")))
    link = item.get("url", item.get("link", ""))
    if not text or not link:
        return None

    tweet_dt = parse_twitter_datetime(item.get("created_at", item.get("createdAt", "")))
    if not within_hours(tweet_dt, cutoff):
        return None

    likes = int(item.get("likes", item.get("like_count", 0)) or 0)
    retweets = int(item.get("retweets", item.get("retweet_count", 0)) or 0)
    replies = int(item.get("replies", item.get("reply_count", 0)) or 0)
    quotes = int(item.get("quotes", item.get("quote_count", 0)) or 0)
    impressions = item.get("impressions", item.get("impression_count"))

    article = {
        "title": text,
        "link": link,
        "date": tweet_dt.isoformat(),
        "topic": topic_id,
        "summary": text,
        "metrics": {
            "like_count": likes,
            "retweet_count": retweets,
            "reply_count": replies,
            "quote_count": quotes,
            "impression_count": impressions,
        },
        "tweet_id": item.get("id"),
        "tweet_type": item.get("type"),
        "author": item.get("author") or item.get("username"),
        "rt_author": item.get("rt_author"),
    }
    if query:
        article["twitter_query"] = query
    return article


def fetch_timeline(source: Dict[str, Any]) -> Dict[str, Any]:
    handle = source.get("handle")
    if not handle:
        raise ValueError(f"Twitter source missing handle: {source.get('id', 'unknown')}")
    count = timeline_count_for_source(source)
    return run_bb_browser_site(["twitter/tweets", handle, str(count)])


def fetch_source(source: Dict[str, Any], cutoff: datetime) -> Dict[str, Any]:
    try:
        payload = fetch_timeline(source)
        articles = []
        for item in extract_tweets(payload):
            article = parse_tweet(item, get_source_topic(source), cutoff)
            if article:
                articles.append(article)
        return {
            "source_id": source.get("id"),
            "source_type": "twitter",
            "name": source.get("name", source.get("id", "unknown")),
            "handle": source.get("handle"),
            "priority": source.get("priority", 3),
            "topic": get_source_topic(source),
            "status": "ok",
            "attempts": 1,
            "items": len(articles),
            "count": len(articles),
            "articles": articles,
        }
    except Exception as exc:
        return {
            "source_id": source.get("id"),
            "source_type": "twitter",
            "name": source.get("name", source.get("id", "unknown")),
            "handle": source.get("handle"),
            "priority": source.get("priority", 3),
            "topic": get_source_topic(source),
            "status": "error",
            "attempts": 1,
            "error": str(exc)[:200],
            "items": 0,
            "count": 0,
            "articles": [],
        }


def fetch_topic(topic: Dict[str, Any], cutoff: datetime, logger: logging.Logger) -> Dict[str, Any]:
    search = topic.get("search", {})
    queries = search.get("twitter_queries", [])
    exclude = search.get("exclude", [])
    per_query = result_count_for_topic(topic)

    query_stats = []
    dedup_by_url: Dict[str, Dict[str, Any]] = {}

    for query in queries:
        compiled_query = build_twitter_query(query, exclude)
        try:
            payload = run_bb_browser_site(["twitter/search", compiled_query, str(per_query), "latest"])
            tweets = extract_tweets(payload)
            kept = 0
            for item in tweets:
                article = parse_tweet(item, topic.get("id"), cutoff, compiled_query)
                if not article:
                    continue
                dedup_by_url.setdefault(article["link"], article)
                kept += 1
            query_stats.append({"query": compiled_query, "status": "ok", "count": kept})
        except Exception as exc:
            logger.warning("Twitter query failed [%s]: %s", topic.get("id"), exc)
            query_stats.append({"query": compiled_query, "status": "error", "count": 0, "error": str(exc)[:200]})

    articles = list(dedup_by_url.values())
    articles.sort(key=lambda article: article.get("date", ""), reverse=True)
    ok_queries = sum(1 for stat in query_stats if stat["status"] == "ok")
    return {
        "topic_id": topic.get("id"),
        "status": "ok" if articles else "error",
        "queries_executed": len(queries),
        "queries_ok": ok_queries,
        "query_stats": query_stats,
        "items": len(articles),
        "count": len(articles),
        "articles": articles,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Twitter/X timelines and topic-query search results via bb-browser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 fetch-twitter.py --defaults config/defaults --config workspace/config --hours 48 --output twitter.json
    python3 fetch-twitter.py --output twitter.json --verbose
        """,
    )
    parser.add_argument("--defaults", type=Path, default=Path("config/defaults"), help="Default configuration directory")
    parser.add_argument("--config", type=Path, help="User configuration directory for overlays")
    parser.add_argument("--hours", type=int, default=48, help="Time window in hours")
    parser.add_argument("--output", "-o", type=Path, help="Output JSON path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--force", action="store_true", help="Accepted for CLI consistency; this fetcher always refreshes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logging(args.verbose)
    if not args.output:
        fd, temp_path = tempfile.mkstemp(prefix="news-hotspots-twitter-", suffix=".json")
        os.close(fd)
        args.output = Path(temp_path)

    try:
        sources = load_sources(args.defaults, args.config)
        topics = load_merged_topics(args.defaults, args.config)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        logger.info("Fetching %d Twitter sources and %d topic query groups sequentially", len(sources), len(topics))
        logger.info("Twitter bb-browser cooldown: %.1fs", COOLDOWN_SECONDS)

        source_results = [fetch_source(source, cutoff) for source in sources]
        for result in source_results:
            if result["status"] == "ok":
                logger.info("✅ %s: %d tweets", result["name"], result["count"])
            else:
                logger.warning("❌ %s: %s", result["name"], result.get("error"))

        topic_results = [fetch_topic(topic, cutoff, logger) for topic in topics if topic.get("search", {}).get("twitter_queries")]
        ok_sources = sum(1 for result in source_results if result["status"] == "ok")
        ok_topics = sum(1 for result in topic_results if result["status"] == "ok")
        total_query_calls = sum(len(result.get("query_stats", [])) for result in topic_results)
        ok_query_calls = sum(
            1
            for result in topic_results
            for stat in result.get("query_stats", [])
            if isinstance(stat, dict) and stat.get("status") == "ok"
        )
        total_articles = sum(result.get("count", 0) for result in source_results) + sum(result.get("count", 0) for result in topic_results)
        total_calls = len(source_results) + total_query_calls
        ok_calls = ok_sources + ok_query_calls

        output = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "source_type": "twitter",
            "backend": "bb-browser",
            "defaults_dir": str(args.defaults),
            "config_dir": str(args.config) if args.config else None,
            "hours": args.hours,
            "calls_total": total_calls,
            "calls_ok": ok_calls,
            "calls_kind": "mixed",
            "items_total": total_articles,
            "sources_total": len(source_results),
            "sources_ok": ok_sources,
            "topics_total": len(topic_results),
            "topics_ok": ok_topics,
            "queries_total": total_query_calls,
            "queries_ok": ok_query_calls,
            "total_articles": total_articles,
            "sources": source_results,
            "topics": topic_results,
        }
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)

        logger.info(
            "✅ Done: %d/%d sources ok, %d/%d query groups ok, %d tweets → %s",
            ok_sources,
            len(source_results),
            ok_topics,
            len(topic_results),
            total_articles,
            args.output,
        )
        return 0 if ok_sources == len(source_results) and ok_topics == len(topic_results) else 1
    except Exception as exc:
        logger.error("💥 Twitter fetch failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
