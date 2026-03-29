#!/usr/bin/env python3
"""Tests for fetch-twitter.py."""

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-twitter.py"

spec = importlib.util.spec_from_file_location("fetch_twitter", MODULE_PATH)
fetch_twitter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_twitter)


class TestFetchTwitter(unittest.TestCase):
    def test_parse_twitter_datetime(self):
        dt = fetch_twitter.parse_twitter_datetime("Fri Mar 27 05:10:30 +0000 2026")
        self.assertEqual(dt.isoformat(), "2026-03-27T05:10:30+00:00")

    def test_parse_tweet_filters_out_old_items(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        article = fetch_twitter.parse_tweet(
            {
                "id": "1",
                "url": "https://x.com/sama/status/1",
                "text": "old tweet",
                "created_at": "Fri Mar 07 05:10:30 +0000 2025",
                "likes": 1,
                "retweets": 2,
            },
            {"topic": "ai-frontier"},
            cutoff,
        )
        self.assertIsNone(article)

    def test_parse_tweet_keeps_recent_metrics(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24 * 365)
        article = fetch_twitter.parse_tweet(
            {
                "id": "1",
                "url": "https://x.com/sama/status/1",
                "text": "hello world",
                "created_at": "Fri Mar 27 05:10:30 +0000 2026",
                "likes": 10,
                "retweets": 2,
                "replies": 3,
            },
            {"topic": "ai-frontier"},
            cutoff,
        )
        self.assertEqual(article["metrics"]["like_count"], 10)
        self.assertEqual(article["metrics"]["reply_count"], 3)
        self.assertEqual(article["tweet_id"], "1")

    def test_fetch_timeline_uses_twitter_tweets_adapter(self):
        source = {"id": "sama-twitter", "handle": "sama", "limit": 5}
        with patch.object(fetch_twitter, "run_bb_browser_site", return_value={"tweets": []}) as run_mock:
            fetch_twitter.fetch_timeline(source)

        run_mock.assert_called_once_with(["twitter/tweets", "sama", "5"])


if __name__ == "__main__":
    unittest.main()
