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
            {"topics": ["ai-models"], "min_score": 50},
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
            {"topics": ["ai-models"], "min_score": 50},
        )
        self.assertEqual(article["reddit_url"], "https://www.reddit.com/r/OpenAI/comments/abc/openai_ships_something/")
        self.assertEqual(article["link"], "https://example.com/article")

    def test_fetch_search_source_uses_serial_search_command(self):
        source = {
            "id": "reddit-openai-search",
            "query": "OpenAI",
            "subreddit": "OpenAI",
            "sort": "top",
            "time": "week",
            "limit": 10,
        }
        with patch.object(fetch_reddit, "run_bb_browser_site", return_value={"items": []}) as run_mock:
            fetch_reddit.fetch_search_source(source, hours=48)

        run_mock.assert_called_once_with(
            ["reddit/search", "OpenAI", "OpenAI", "--sort", "top", "--time", "week", "10"]
        )

    def test_fetch_hot_source_uses_hot_command(self):
        source = {"id": "reddit-openai", "subreddit": "OpenAI", "limit": 5}
        with patch.object(fetch_reddit, "run_bb_browser_site", return_value={"items": []}) as run_mock:
            fetch_reddit.fetch_hot_source(source)

        run_mock.assert_called_once_with(["reddit/hot", "OpenAI", "5"])


if __name__ == "__main__":
    unittest.main()
