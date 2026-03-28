#!/usr/bin/env python3
"""Tests for fetch-github.py."""

import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-github.py"
DEFAULTS_DIR = Path(__file__).parent.parent / "config" / "defaults"

spec = importlib.util.spec_from_file_location("fetch_github", MODULE_PATH)
fetch_github = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_github)


class FakeHeaders:
    def get(self, key, default=None):
        return default


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.headers = FakeHeaders()

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestFetchGitHub(unittest.TestCase):
    def test_load_sources_returns_github_only_topics(self):
        sources = fetch_github.load_sources(DEFAULTS_DIR)

        self.assertTrue(sources)
        self.assertTrue(all(source["type"] == "github" for source in sources))
        self.assertTrue(all(source.get("topics") == ["github"] for source in sources))

    def test_fetch_releases_preserves_single_github_topic(self):
        source = {
            "id": "ollama-github",
            "name": "Ollama",
            "repo": "ollama/ollama",
            "priority": 8,
            "topics": ["github"],
        }
        cutoff = datetime(2026, 3, 27, 0, 0, tzinfo=timezone.utc)
        payload = [
            {
                "tag_name": "v0.18.0",
                "html_url": "https://github.com/ollama/ollama/releases/tag/v0.18.0",
                "body": "Improves model serving and structured outputs.",
                "published_at": "2026-03-28T03:12:00Z",
                "draft": False,
            }
        ]

        with patch.object(fetch_github, "urlopen", return_value=FakeResponse(payload)):
            result = fetch_github.fetch_releases_with_retry(
                source,
                cutoff,
                github_token=None,
                no_cache=True,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["topics"], ["github"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["topics"], ["github"])
        self.assertEqual(result["articles"][0]["title"], "ollama v0.18.0")


if __name__ == "__main__":
    unittest.main()
