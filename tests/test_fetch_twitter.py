#!/usr/bin/env python3
"""Tests for fetch-twitter.py."""

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-twitter.py"

spec = importlib.util.spec_from_file_location("fetch_twitter", MODULE_PATH)
fetch_twitter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_twitter)


class TestFetchTwitter(unittest.TestCase):
    def test_build_twitter_query_appends_excluded_terms(self):
        query = fetch_twitter.build_twitter_query(
            "Tesla robotaxi",
            ["rumor", "game review"],
        )
        self.assertEqual(query, 'Tesla robotaxi -rumor -"game review"')

    def test_parse_twitter_datetime(self):
        dt = fetch_twitter.parse_twitter_datetime("Fri Mar 27 05:10:30 +0000 2026")
        self.assertEqual(dt.isoformat(), "2026-03-27T05:10:30+00:00")

    def test_parse_tweet_filters_out_old_items(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        article = fetch_twitter.parse_tweet(
            {
                "id": "1",
                "url": "https://x.com/tesla/status/1",
                "text": "old tweet",
                "created_at": "Fri Mar 07 05:10:30 +0000 2025",
                "likes": 1,
            },
            "ai-infra",
            cutoff,
            "Tesla",
        )
        self.assertIsNone(article)

    def test_parse_tweet_keeps_recent_metrics(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24 * 365)
        article = fetch_twitter.parse_tweet(
            {
                "id": "1",
                "url": "https://x.com/tesla/status/1",
                "text": "hello world",
                "created_at": "Fri Mar 27 05:10:30 +0000 2026",
                "likes": 10,
                "retweets": 2,
                "replies": 3,
            },
            "ai-infra",
            cutoff,
            "Tesla",
        )
        self.assertEqual(article["metrics"]["like_count"], 10)
        self.assertEqual(article["metrics"]["reply_count"], 3)
        self.assertEqual(article["tweet_id"], "1")
        self.assertEqual(article["twitter_query"], "Tesla")

    def test_fetch_source_uses_twitter_tweets_adapter(self):
        source = {"id": "tesla-twitter", "handle": "tesla", "limit": 5, "topic": "ai-infra"}
        payload = {
            "tweets": [
                {
                    "id": "1",
                    "url": "https://x.com/tesla/status/1",
                    "text": "Tesla update",
                    "created_at": "Fri Mar 27 05:10:30 +0000 2026",
                }
            ]
        }
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24 * 365)
        with patch.object(fetch_twitter, "run_bb_browser_site", return_value=payload) as run_mock:
            result = fetch_twitter.fetch_source(source, cutoff)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertIn("elapsed_s", result)
        self.assertEqual(result["request_timing_summary"]["requests_total"], 1)
        self.assertIn("timed_request", result["timing_keywords"])
        run_mock.assert_called_once_with(["twitter/tweets", "tesla", "5"])

    def test_extract_tweets_supports_items_payload(self):
        tweets = fetch_twitter.extract_tweets({"items": [{"id": "1"}, {"id": "2"}]})
        self.assertEqual(len(tweets), 2)

    def test_fetch_topic_aggregates_queries(self):
        topic = {
            "id": "ai-infra",
            "search": {
                "twitter_queries": ["Tesla", "robotics"],
                "exclude": ["rumor"],
            },
            "display": {"max_items": 2},
        }
        payload = {
            "items": [
                {
                    "id": "1",
                    "url": "https://x.com/tesla/status/1",
                    "text": "Tesla robotaxi update",
                    "created_at": "Fri Mar 27 05:10:30 +0000 2026",
                    "likes": 10,
                },
                {
                    "id": "1b",
                    "url": "https://x.com/tesla/status/1",
                    "text": "Tesla robotaxi update duplicate",
                    "created_at": "Fri Mar 27 05:10:30 +0000 2026",
                    "likes": 11,
                },
            ]
        }
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24 * 365)
        with patch.object(fetch_twitter, "run_bb_browser_site", return_value=payload) as run_mock:
            result = fetch_twitter.fetch_topic(topic, cutoff, fetch_twitter.logging.getLogger("test"))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["queries_ok"], 2)
        self.assertEqual(len(result["request_timings"]), 2)
        self.assertIn("timed_request", result["query_stats"][0]["timing_keywords"])
        run_mock.assert_any_call(["twitter/search", "Tesla -rumor", "2", "latest"])
        run_mock.assert_any_call(["twitter/search", "robotics -rumor", "2", "latest"])

    def test_run_bb_browser_site_parses_json_and_updates_cooldown(self):
        completed = MagicMock(returncode=0, stdout='{"items": []}', stderr="")
        with patch.object(fetch_twitter.subprocess, "run", return_value=completed) as run_mock:
            with patch.object(fetch_twitter, "throttle_after_success") as throttle_mock:
                fetch_twitter._last_success_at = None
                payload = fetch_twitter.run_bb_browser_site(["twitter/search", "Tesla", "5", "latest"])

        self.assertEqual(payload, {"items": []})
        run_mock.assert_called_once()
        throttle_mock.assert_called_once()
        self.assertIsNotNone(fetch_twitter._last_success_at)


if __name__ == "__main__":
    unittest.main()
