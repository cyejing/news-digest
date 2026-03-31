#!/usr/bin/env python3
"""Tests for fetch-v2ex.py."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-v2ex.py"

spec = importlib.util.spec_from_file_location("fetch_v2ex", MODULE_PATH)
fetch_v2ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_v2ex)


class TestFetchV2EX(unittest.TestCase):
    def test_transform_topic_uses_fixed_technology_topic(self):
        article = fetch_v2ex.transform_topic(
            {
                "id": 1,
                "title": "2026 年，node 写后端你用的 nestjs, fastify, honojs 还是其他？",
                "content": "",
                "node": "Node.js",
                "nodeSlug": "nodejs",
                "author": "alice",
                "replies": 90,
                "created": 1774574654,
                "url": "https://www.v2ex.com/t/1",
            }
        )

        self.assertIsNotNone(article)
        self.assertEqual(article["topic"], "technology")
        self.assertEqual(article["replies"], 90)

    def test_transform_topic_keeps_non_tech_threads_with_technology_topic(self):
        article = fetch_v2ex.transform_topic(
            {
                "id": 2,
                "title": "昨晚买了人生中的第一套房",
                "content": "纯生活分享",
                "node": "生活",
                "nodeSlug": "life",
                "author": "bob",
                "replies": 270,
                "created": 1774594066,
                "url": "https://www.v2ex.com/t/2",
            }
        )

        self.assertIsNotNone(article)
        self.assertEqual(article["topic"], "technology")

    def test_run_bb_browser_site_parses_json_and_updates_cooldown(self):
        completed = MagicMock(returncode=0, stdout='{"topics": []}', stderr="")
        with patch.object(fetch_v2ex.subprocess, "run", return_value=completed) as run_mock:
            with patch.object(fetch_v2ex, "throttle_after_success") as throttle_mock:
                fetch_v2ex._last_success_at = None
                payload = fetch_v2ex.run_bb_browser_site(["v2ex/hot"])

        self.assertEqual(payload, {"topics": []})
        run_mock.assert_called_once()
        throttle_mock.assert_called_once()
        self.assertIsNotNone(fetch_v2ex._last_success_at)


if __name__ == "__main__":
    unittest.main()
