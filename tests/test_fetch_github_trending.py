#!/usr/bin/env python3
"""Tests for fetch-github-trending.py."""

import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-github-trending.py"
DEFAULTS_DIR = Path(__file__).parent.parent / "config" / "defaults"

spec = importlib.util.spec_from_file_location("fetch_github_trending", MODULE_PATH)
fetch_github_trending = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_github_trending)


class TestFetchGithubTrending(unittest.TestCase):
    def test_load_queries_only_reads_github_topic(self):
        queries = fetch_github_trending.load_github_trending_queries(DEFAULTS_DIR)
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0]["topic"], "github")

    def test_trending_results_only_use_github_topic(self):
        payload = {
            "items": [
                {
                    "full_name": "example/project",
                    "name": "project",
                    "description": "Example repo",
                    "html_url": "https://github.com/example/project",
                    "stargazers_count": 1200,
                    "forks_count": 100,
                    "language": "Python",
                    "created_at": "2025-01-01T00:00:00Z",
                    "pushed_at": "2026-03-28T00:00:00Z",
                }
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        with patch.object(fetch_github_trending, "urlopen", return_value=FakeResponse()):
            with patch.object(fetch_github_trending.time, "sleep", return_value=None):
                repos = fetch_github_trending.fetch_trending_repos(
                    hours=48,
                    github_token=None,
                    defaults_dir=None,
                    config_dir=None,
                )

        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]["topics"], ["github"])


if __name__ == "__main__":
    unittest.main()
