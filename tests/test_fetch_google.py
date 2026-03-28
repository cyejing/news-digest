#!/usr/bin/env python3
"""Tests for fetch-google.py."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-google.py"

spec = importlib.util.spec_from_file_location("fetch_google", MODULE_PATH)
fetch_google = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_google)


class TestFetchGoogle(unittest.TestCase):
    def test_build_google_query_appends_excluded_terms(self):
        query = fetch_google.build_google_query(
            "OpenAI latest",
            ["tutorial", "beginner guide"],
        )
        self.assertEqual(
            query,
            'OpenAI latest -tutorial -"beginner guide"',
        )

    def test_fetch_topic_aggregates_queries(self):
        topic = {
            "id": "ai-models",
            "search": {
                "queries": ["OpenAI", "Anthropic"],
                "exclude": ["tutorial"],
            },
            "display": {"max_items": 2},
        }
        payload = {
            "results": [
                {"title": "OpenAI model update", "url": "https://example.com/1", "snippet": "hi", "source": "Example", "timestamp": 1774614526},
                {"title": "OpenAI model update", "url": "https://example.com/1", "snippet": "dup", "source": "Example", "timestamp": 1774614526},
            ]
        }
        with patch.object(fetch_google, "run_bb_browser_site", return_value=payload) as run_mock:
            result = fetch_google.fetch_topic(topic, fetch_google.logging.getLogger("test"))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["queries_ok"], 2)
        run_mock.assert_any_call(
            ["google/news", "OpenAI -tutorial", "2"]
        )


if __name__ == "__main__":
    unittest.main()
