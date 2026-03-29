#!/usr/bin/env python3
"""Tests for fetch-api.py."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-api.py"

spec = importlib.util.spec_from_file_location("fetch_api", MODULE_PATH)
fetch_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_api)


class TestFetchApi(unittest.TestCase):
    def test_load_api_sources_includes_hacker_news(self):
        sources = fetch_api.load_api_sources(fetch_api.Path("config/defaults"))
        ids = [source["id"] for source in sources]
        self.assertIn("hacker-news-api", ids)

    def test_fetch_hacker_news_builds_story_articles(self):
        def fake_http_get_json(url, headers=None, timeout=fetch_api.TIMEOUT):
            if url.endswith("/beststories.json"):
                return [101, 102, 103]
            if url.endswith("/item/101.json"):
                return {
                    "id": 101,
                    "type": "story",
                    "title": "HN story one",
                    "url": "https://example.com/one",
                    "time": 1774614526,
                    "score": 123,
                    "descendants": 45,
                    "by": "alice",
                }
            if url.endswith("/item/102.json"):
                return {
                    "id": 102,
                    "type": "job",
                    "title": "ignore job posts",
                }
            if url.endswith("/item/103.json"):
                return {
                    "id": 103,
                    "type": "story",
                    "title": "HN story two",
                    "time": 1774615526,
                    "score": 88,
                    "descendants": 12,
                    "by": "bob",
                }
            raise AssertionError(f"unexpected url {url}")

        with patch.object(fetch_api, "http_get_json", side_effect=fake_http_get_json):
            articles = fetch_api.fetch_hacker_news(limit=2)

        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["source_id"], "hacker-news-api")
        self.assertNotIn("topic", articles[0])
        self.assertEqual(articles[0]["score"], 123)
        self.assertEqual(articles[0]["comments"], 45)
        self.assertEqual(
            articles[1]["link"],
            "https://news.ycombinator.com/item?id=103",
        )

    def test_fetch_source_applies_topic_from_config(self):
        source = {
            "id": "hacker-news-api",
            "name": "Hacker News API",
            "topic": "technology",
            "priority": 4,
        }
        with patch.object(fetch_api, "fetch_hacker_news", return_value=[{"title": "A", "link": "https://example.com"}]):
            result = fetch_api.fetch_source(source, limit=1, topic_rules={"topic_priority": ["technology"]})

        self.assertEqual(result["topic"], "technology")
        self.assertEqual(result["articles"][0]["topic"], "technology")


if __name__ == "__main__":
    unittest.main()
