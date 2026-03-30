#!/usr/bin/env python3
"""Tests for fetch-reddit.py."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-reddit.py"

spec = importlib.util.spec_from_file_location("fetch_reddit", MODULE_PATH)
fetch_reddit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_reddit)


class TestFetchReddit(unittest.TestCase):
    def test_source_mode_prefers_search_when_query_present(self):
        self.assertEqual(fetch_reddit.source_mode({"query": "openai"}), "search")
        self.assertEqual(fetch_reddit.source_mode({"search_query": "openai"}), "search")
        self.assertEqual(fetch_reddit.source_mode({"subreddit": "OpenAI"}), "hot")

    def test_parse_post_filters_min_score(self):
        article = fetch_reddit.parse_post(
            {
                "title": "OpenAI ships something",
                "url": "https://example.com/article",
                "permalink": "/r/OpenAI/comments/abc/openai_ships_something/",
                "created_utc": 1774577508,
                "score": 10,
                "num_comments": 5,
                "selftext": "",
            },
            {"topic": "ai-frontier", "min_score": 50},
        )
        self.assertIsNone(article)

    def test_parse_post_normalizes_reddit_links(self):
        article = fetch_reddit.parse_post(
            {
                "title": "OpenAI ships something",
                "url": "https://example.com/article",
                "permalink": "/r/OpenAI/comments/abc/openai_ships_something/",
                "created_utc": 1774577508,
                "score": 80,
                "num_comments": 12,
                "selftext": "summary",
            },
            {"topic": "ai-frontier", "min_score": 50},
        )
        self.assertEqual(article["reddit_url"], "https://www.reddit.com/r/OpenAI/comments/abc/openai_ships_something/")
        self.assertEqual(article["link"], "https://example.com/article")

    def test_fetch_search_source_uses_serial_search_command(self):
        source = {
            "id": "reddit-openai-search",
            "query": "OpenAI",
            "sort": "top",
            "time": "week",
            "limit": 10,
        }
        with patch.object(fetch_reddit, "run_bb_browser_site", return_value={"items": []}) as run_mock:
            fetch_reddit.fetch_search_source(source, hours=48)

        run_mock.assert_called_once_with(
            ["reddit/search", "OpenAI", "--sort", "top", "--time", "week", "--count", "10"]
        )

    def test_fetch_hot_source_uses_hot_command(self):
        source = {"id": "reddit-openai", "subreddit": "OpenAI", "limit": 5}
        with patch.object(fetch_reddit, "run_bb_browser_site", return_value={"items": []}) as run_mock:
            fetch_reddit.fetch_hot_source(source)

        run_mock.assert_called_once_with(["reddit/hot", "OpenAI", "5"])

    def test_fetch_topic_uses_reddit_queries(self):
        topic = {
            "id": "ai-frontier",
            "search": {
                "reddit_queries": ["OpenAI", "Anthropic"],
                "exclude": ["tutorial"],
            },
            "display": {"max_items": 2},
        }
        payload = {
            "items": [
                {
                    "title": "OpenAI ships something",
                    "url": "https://example.com/article",
                    "permalink": "/r/OpenAI/comments/abc/openai_ships_something/",
                    "created_utc": 1774577508,
                    "score": 80,
                    "num_comments": 12,
                    "selftext": "summary",
                }
            ]
        }
        with patch.object(fetch_reddit, "run_bb_browser_site", return_value=payload) as run_mock:
            result = fetch_reddit.fetch_topic(topic, hours=48, logger=fetch_reddit.logging.getLogger("test"))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["request_timings"]), 2)
        self.assertIn("timed_request", result["query_stats"][0]["timing_keywords"])
        run_mock.assert_any_call(["reddit/search", 'OpenAI -tutorial', "--sort", "top", "--time", "week", "--count", "2"])

    def test_parse_post_accepts_topic_id_string(self):
        article = fetch_reddit.parse_post(
            {
                "title": "OpenAI ships something",
                "url": "https://example.com/article",
                "permalink": "/r/OpenAI/comments/abc/openai_ships_something/",
                "created_utc": 1774577508,
                "score": 80,
                "num_comments": 12,
                "selftext": "summary",
            },
            "ai-frontier",
            50,
            "OpenAI",
        )
        self.assertEqual(article["topic"], "ai-frontier")
        self.assertEqual(article["reddit_query"], "OpenAI")

    def test_fetch_source_adds_request_timing_fields(self):
        source = {"id": "reddit-openai", "subreddit": "OpenAI", "topic": "ai-frontier", "limit": 5}
        payload = {
            "items": [
                {
                    "title": "OpenAI ships something",
                    "url": "https://example.com/article",
                    "permalink": "/r/OpenAI/comments/abc/openai_ships_something/",
                    "created_utc": 1774577508,
                    "score": 80,
                    "num_comments": 12,
                    "selftext": "summary",
                }
            ]
        }
        with patch.object(fetch_reddit, "run_bb_browser_site", return_value=payload):
            result = fetch_reddit.fetch_source(source, hours=48)

        self.assertEqual(result["status"], "ok")
        self.assertIn("elapsed_s", result)
        self.assertIn("timed_request", result["timing_keywords"])
        self.assertEqual(result["request_timing_summary"]["requests_total"], 1)


if __name__ == "__main__":
    unittest.main()
