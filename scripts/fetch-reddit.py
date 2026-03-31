#!/usr/bin/env python3
"""
Fetch Reddit posts via bb-browser site adapters.

Reads source-mode entries from sources.json and topic query lists from
topics.json. Both modes run sequentially in one step and share one cooldown.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from config_loader import load_merged_sources, load_merged_topics
    from fetch_timing import build_request_trace, summarize_request_traces
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from config_loader import load_merged_sources, load_merged_topics
    from fetch_timing import build_request_trace, summarize_request_traces

try:
    from topic_utils import get_source_topic
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from topic_utils import get_source_topic

COOLDOWN_SECONDS = float(os.environ.get("BB_BROWSER_REDDIT_COOLDOWN_SECONDS", "6.0"))
DEFAULT_TIMEOUT = 180
DEFAULT_RESULTS_PER_QUERY = 10
MAX_RESULTS_PER_QUERY = 20
_last_success_at: Optional[float] = None
_reddit_search_block_reason: Optional[str] = None


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


def is_blocking_reddit_search_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "http 403" in message and "please log in to https://www.reddit.com" in message


def load_sources(defaults_dir: Path, config_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    all_sources = load_merged_sources(defaults_dir, config_dir)
    return [source for source in all_sources if source.get("type") == "reddit" and source.get("enabled", True)]


def source_mode(source: Dict[str, Any]) -> str:
    if source.get("query") or source.get("search_query"):
        return "search"
    return "hot"


def hours_to_reddit_time(hours: int) -> str:
    if hours <= 24:
        return "day"
    if hours <= 24 * 7:
        return "week"
    if hours <= 24 * 30:
        return "month"
    if hours <= 24 * 365:
        return "year"
    return "all"


def result_count_for_topic(topic: Dict[str, Any]) -> int:
    display = topic.get("display", {})
    max_items = display.get("max_items", DEFAULT_RESULTS_PER_QUERY)
    try:
        return max(1, min(MAX_RESULTS_PER_QUERY, int(max_items)))
    except (TypeError, ValueError):
        return DEFAULT_RESULTS_PER_QUERY


def extract_posts(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    for key in ("posts", "results", "items", "children", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for nested_key in ("children", "items", "posts"):
                nested_value = value.get(nested_key)
                if isinstance(nested_value, list):
                    return nested_value
    return []


def parse_post(
    item: Dict[str, Any],
    topic_or_source: Any,
    min_score: int = 0,
    query: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if isinstance(topic_or_source, dict):
        topic_id = get_source_topic(topic_or_source)
        min_score = int(topic_or_source.get("min_score", min_score) or 0)
        if query is None:
            query = topic_or_source.get("query") or topic_or_source.get("search_query")
    else:
        topic_id = str(topic_or_source or "")

    data = item.get("data") if isinstance(item.get("data"), dict) else item
    title = (data.get("title") or "").strip()
    if not title:
        return None

    permalink = data.get("permalink") or data.get("reddit_url") or data.get("url")
    if permalink and permalink.startswith("/"):
        reddit_url = f"https://www.reddit.com{permalink}"
    else:
        reddit_url = permalink or ""
    external_url = data.get("external_url")
    if not external_url:
        url = data.get("url") or ""
        external_url = url if not url.startswith("/r/") else None

    link = external_url or reddit_url
    if not link:
        return None

    created = data.get("created_utc")
    if created is None:
        created = data.get("created")
    date_iso = ""
    if isinstance(created, (int, float)):
        date_iso = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()

    score = int(data.get("score", 0) or 0)
    num_comments = int(data.get("num_comments", data.get("comments", data.get("comment_count", 0))) or 0)
    if score < int(min_score or 0):
        return None

    flair = data.get("link_flair_text") or data.get("flair")
    is_self = bool(data.get("is_self", False))
    summary = (data.get("selftext") or data.get("text") or data.get("snippet") or "").strip()

    article = {
        "title": title,
        "link": link,
        "reddit_url": reddit_url,
        "external_url": external_url,
        "date": date_iso,
        "score": score,
        "num_comments": num_comments,
        "flair": flair,
        "is_self": is_self,
        "summary": summary[:400],
        "topic": topic_id,
        "metrics": {
            "score": score,
            "num_comments": num_comments,
            "upvote_ratio": data.get("upvote_ratio"),
        },
    }
    if query:
        article["reddit_query"] = query
    return article


def fetch_hot_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    subreddit = source.get("subreddit")
    limit = int(source.get("limit", 25) or 25)
    args = ["reddit/hot"]
    if subreddit:
        args.append(subreddit)
    args.append(str(limit))
    payload = run_bb_browser_site(args)
    return extract_posts(payload)


def fetch_search_source(source: Dict[str, Any], hours: int) -> List[Dict[str, Any]]:
    query = source.get("query") or source.get("search_query")
    if not query:
        raise ValueError(f"Reddit search source missing query: {source.get('id', 'unknown')}")

    limit = int(source.get("limit", 25) or 25)
    sort = source.get("sort", "relevance") or "relevance"
    time_filter = source.get("time") or hours_to_reddit_time(hours)

    args = ["reddit/search", str(query), "--sort", str(sort), "--time", str(time_filter), "--count", str(limit)]
    payload = run_bb_browser_site(args)
    return extract_posts(payload)


def fetch_source(source: Dict[str, Any], hours: int) -> Dict[str, Any]:
    mode = source_mode(source)
    started_at = time.monotonic()
    try:
        raw_posts = fetch_search_source(source, hours) if mode == "search" else fetch_hot_source(source)
        articles = []
        for item in raw_posts:
            article = parse_post(item, get_source_topic(source), int(source.get("min_score", 0) or 0), source.get("query") or source.get("search_query"))
            if article:
                articles.append(article)
        elapsed_s = time.monotonic() - started_at
        request_trace = build_request_trace(
            source.get("query") or source.get("subreddit") or source.get("id", "unknown"),
            elapsed_s,
            status="ok",
            backend="bb-browser",
            adapter="reddit/search" if mode == "search" else "reddit/hot",
        )

        return {
            "source_id": source.get("id"),
            "source_type": "reddit",
            "name": source.get("name", source.get("id", "unknown")),
            "subreddit": source.get("subreddit"),
            "query": source.get("query") or source.get("search_query"),
            "sort": source.get("sort", "hot"),
            "mode": mode,
            "priority": source.get("priority", 3),
            "topic": get_source_topic(source),
            "status": "ok",
            "attempts": 1,
            "elapsed_s": round(elapsed_s, 3),
            "timing_keywords": request_trace["timing_keywords"],
            "items": len(articles),
            "count": len(articles),
            "articles": articles,
            "request_timings": [request_trace],
            "request_timing_summary": summarize_request_traces([request_trace]),
        }
    except Exception as exc:
        elapsed_s = time.monotonic() - started_at
        request_trace = build_request_trace(
            source.get("query") or source.get("subreddit") or source.get("id", "unknown"),
            elapsed_s,
            status="error",
            backend="bb-browser",
            adapter="reddit/search" if mode == "search" else "reddit/hot",
            error=str(exc)[:200],
        )
        return {
            "source_id": source.get("id"),
            "source_type": "reddit",
            "name": source.get("name", source.get("id", "unknown")),
            "subreddit": source.get("subreddit"),
            "query": source.get("query") or source.get("search_query"),
            "sort": source.get("sort", "hot"),
            "mode": mode,
            "priority": source.get("priority", 3),
            "topic": get_source_topic(source),
            "status": "error",
            "attempts": 1,
            "error": str(exc)[:200],
            "elapsed_s": round(elapsed_s, 3),
            "timing_keywords": request_trace["timing_keywords"],
            "items": 0,
            "count": 0,
            "articles": [],
            "request_timings": [request_trace],
            "request_timing_summary": summarize_request_traces([request_trace]),
        }


def fetch_topic(topic: Dict[str, Any], hours: int, logger: logging.Logger) -> Dict[str, Any]:
    global _reddit_search_block_reason
    search = topic.get("search", {})
    queries = search.get("reddit_queries", [])
    exclude = search.get("exclude", [])
    per_query = result_count_for_topic(topic)
    time_filter = hours_to_reddit_time(hours)

    query_stats = []
    dedup_by_url: Dict[str, Dict[str, Any]] = {}
    request_timings: List[Dict[str, Any]] = []
    started_at = time.monotonic()

    for query in queries:
        if _reddit_search_block_reason:
            logger.warning("Reddit query skipped [%s]: %s", topic.get("id"), _reddit_search_block_reason)
            break
        compiled_query = " ".join([query] + [f'-"{term}"' if " " in term else f"-{term}" for term in exclude if str(term).strip()])
        query_started_at = time.monotonic()
        try:
            payload = run_bb_browser_site(["reddit/search", compiled_query, "--sort", "top", "--time", time_filter, "--count", str(per_query)])
            posts = extract_posts(payload)
            kept = 0
            for item in posts:
                article = parse_post(item, topic.get("id"), 0, compiled_query)
                if not article:
                    continue
                dedup_by_url.setdefault(article["link"], article)
                kept += 1
            elapsed_s = time.monotonic() - query_started_at
            request_timings.append(build_request_trace(compiled_query, elapsed_s, status="ok", backend="bb-browser", adapter="reddit/search"))
            query_stats.append({"query": compiled_query, "status": "ok", "count": kept, "elapsed_s": round(elapsed_s, 3), "timing_keywords": request_timings[-1]["timing_keywords"]})
        except Exception as exc:
            logger.warning("Reddit query failed [%s]: %s", topic.get("id"), exc)
            elapsed_s = time.monotonic() - query_started_at
            request_timings.append(build_request_trace(compiled_query, elapsed_s, status="error", backend="bb-browser", adapter="reddit/search", error=str(exc)[:200]))
            query_stats.append({"query": compiled_query, "status": "error", "count": 0, "error": str(exc)[:200], "elapsed_s": round(elapsed_s, 3), "timing_keywords": request_timings[-1]["timing_keywords"]})
            if is_blocking_reddit_search_error(exc):
                _reddit_search_block_reason = str(exc)[:200]
                break

    articles = list(dedup_by_url.values())
    articles.sort(key=lambda article: article.get("score", 0), reverse=True)
    ok_queries = sum(1 for stat in query_stats if stat["status"] == "ok")
    return {
        "topic_id": topic.get("id"),
        "status": "ok" if articles else "error",
        "queries_executed": len(queries),
        "queries_ok": ok_queries,
        "elapsed_s": round(time.monotonic() - started_at, 3),
        "query_stats": query_stats,
        "request_timings": request_timings,
        "request_timing_summary": summarize_request_traces(request_timings),
        "items": len(articles),
        "count": len(articles),
        "articles": articles,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequential Reddit fetcher via source mode and topic queries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 fetch-reddit.py --defaults config/defaults --config workspace/config --hours 48 --output reddit.json
    python3 fetch-reddit.py --output reddit.json --verbose
        """,
    )
    parser.add_argument("--defaults", type=Path, default=Path("config/defaults"), help="Default configuration directory")
    parser.add_argument("--config", type=Path, help="User configuration directory for overlays")
    parser.add_argument("--hours", type=int, default=48, help="Used for search time mapping")
    parser.add_argument("--output", "-o", type=Path, help="Output JSON path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--force", action="store_true", help="Accepted for CLI consistency; this fetcher always refreshes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logging(args.verbose)
    if not args.output:
        fd, temp_path = tempfile.mkstemp(prefix="news-hotspots-reddit-", suffix=".json")
        os.close(fd)
        args.output = Path(temp_path)

    try:
        sources = load_sources(args.defaults, args.config)
        topics = load_merged_topics(args.defaults, args.config)
        logger.info("Fetching %d Reddit sources and %d topic query groups sequentially", len(sources), len(topics))
        logger.info("Reddit bb-browser cooldown: %.1fs", COOLDOWN_SECONDS)

        source_results = [fetch_source(source, args.hours) for source in sources]
        for result in source_results:
            if result["status"] == "ok":
                logger.info("✅ %s: %d posts", result["name"], result["count"])
            else:
                logger.warning("❌ %s: %s", result["name"], result.get("error"))

        topic_results = [fetch_topic(topic, args.hours, logger) for topic in topics if topic.get("search", {}).get("reddit_queries")]
        ok_sources = sum(1 for result in source_results if result["status"] == "ok")
        ok_topics = sum(1 for result in topic_results if result["status"] == "ok")
        total_query_calls = sum(len(result.get("query_stats", [])) for result in topic_results)
        ok_query_calls = sum(
            1
            for result in topic_results
            for stat in result.get("query_stats", [])
            if isinstance(stat, dict) and stat.get("status") == "ok"
        )
        total_posts = sum(result.get("count", 0) for result in source_results) + sum(result.get("count", 0) for result in topic_results)
        total_calls = len(source_results) + total_query_calls
        ok_calls = ok_sources + ok_query_calls
        all_request_timings = [
            trace
            for result in [*source_results, *topic_results]
            for trace in result.get("request_timings", [])
            if isinstance(trace, dict)
        ]

        output = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "source_type": "reddit",
            "source": "reddit",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "defaults_dir": str(args.defaults),
            "config_dir": str(args.config) if args.config else None,
            "hours": args.hours,
            "calls_total": total_calls,
            "calls_ok": ok_calls,
            "calls_kind": "mixed",
            "items_total": total_posts,
            "sources_total": len(source_results),
            "sources_ok": ok_sources,
            "topics_total": len(topic_results),
            "topics_ok": ok_topics,
            "queries_total": total_query_calls,
            "queries_ok": ok_query_calls,
            "total_articles": total_posts,
            "total_posts": total_posts,
            "request_timing_summary": summarize_request_traces(all_request_timings),
            "sources": source_results,
            "topics": topic_results,
            "subreddits_total": len(source_results),
            "subreddits_ok": ok_sources,
            "subreddits": source_results,
        }
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)

        logger.info(
            "✅ Done: %d/%d sources ok, %d/%d query groups ok, %d posts → %s",
            ok_sources,
            len(source_results),
            ok_topics,
            len(topic_results),
            total_posts,
            args.output,
        )
        return 0 if ok_sources == len(source_results) and ok_topics == len(topic_results) else 1
    except Exception as exc:
        logger.error("💥 Reddit fetch failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
