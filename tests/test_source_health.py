#!/usr/bin/env python3
"""Tests for source-health.py."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "source-health.py"

spec = importlib.util.spec_from_file_location("source_health", MODULE_PATH)
source_health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_health)


class TestSourceHealth(unittest.TestCase):
    def test_normalize_source_records_supports_current_output_types(self):
        google_payload = json.loads((Path(__file__).parent / "fixtures" / "google.json").read_text(encoding="utf-8"))
        github_payload = json.loads((Path(__file__).parent / "fixtures" / "github.json").read_text(encoding="utf-8"))
        reddit_payload = json.loads((Path(__file__).parent / "fixtures" / "reddit.json").read_text(encoding="utf-8"))

        google_records = source_health.normalize_source_records(google_payload, "google")
        github_records = source_health.normalize_source_records(github_payload, "github")
        reddit_records = source_health.normalize_source_records(reddit_payload, "reddit")

        self.assertEqual(google_records[0]["source_id"], "google-ai-models")
        self.assertEqual(github_records[0]["source_type"], "github")
        self.assertEqual(reddit_records[0]["source_type"], "reddit")

    def test_update_and_report_marks_unhealthy_sources(self):
        now = 1_800_000_000
        health = {}
        source_health.update_health(
            health,
            [{"source_id": "rss-a", "name": "RSS A", "source_type": "rss", "status": "error"}],
            now - 10,
        )
        source_health.update_health(
            health,
            [{"source_id": "rss-a", "name": "RSS A", "source_type": "rss", "status": "error"}],
            now,
        )

        rows = source_health.build_report_rows(health, now)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["unhealthy"])
        self.assertEqual(rows[0]["failure_rate"], 1.0)

    def test_main_updates_from_input_dir_and_report_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            health_file = tmp_path / "health.json"
            rss_payload = {
                "sources": [
                    {"source_id": "rss-one", "name": "RSS One", "status": "ok"},
                    {"source_id": "rss-two", "name": "RSS Two", "status": "error"},
                ]
            }
            google_payload = {
                "topics": [
                    {"topic_id": "ai-models", "status": "ok"},
                ]
            }
            (tmp_path / "rss.json").write_text(json.dumps(rss_payload), encoding="utf-8")
            (tmp_path / "google.json").write_text(json.dumps(google_payload), encoding="utf-8")

            old_argv = source_health.sys.argv
            try:
                source_health.sys.argv = [
                    "source-health.py",
                    "--input-dir",
                    str(tmp_path),
                    "--health-file",
                    str(health_file),
                ]
                self.assertEqual(source_health.main(), 0)

                data = json.loads(health_file.read_text(encoding="utf-8"))
                self.assertIn("rss-one", data)
                self.assertIn("google-ai-models", data)

                source_health.sys.argv = [
                    "source-health.py",
                    "--health-file",
                    str(health_file),
                    "--report-only",
                ]
                self.assertEqual(source_health.main(), 0)
            finally:
                source_health.sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
