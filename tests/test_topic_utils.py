#!/usr/bin/env python3
"""Tests for topic_utils.py."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "topic_utils.py"

spec = importlib.util.spec_from_file_location("topic_utils", MODULE_PATH)
topic_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(topic_utils)


class TestTopicUtils(unittest.TestCase):
    def test_resolve_primary_topic_reads_topic_from_record_lists(self):
        items = [
            {"title": "A", "topic": "business"},
            {"title": "B", "topic": "github"},
        ]

        self.assertEqual(topic_utils.resolve_primary_topic(items), "github")

    def test_load_default_topic_rules_prefers_env_paths(self):
        with tempfile.TemporaryDirectory() as defaults_dir, tempfile.TemporaryDirectory() as config_dir:
            (Path(defaults_dir) / "topic-rules.json").write_text(
                json.dumps({"topic_priority": ["social"], "legacy_topic_map": {"old": "social"}}),
                encoding="utf-8",
            )
            (Path(config_dir) / "news-hotspots-topic-rules.json").write_text(
                json.dumps({"topic_priority": ["business", "social"]}),
                encoding="utf-8",
            )
            topic_utils.load_default_topic_rules.cache_clear()
            old_defaults = os.environ.get("NEWS_HOTSPOTS_DEFAULTS_DIR")
            old_config = os.environ.get("NEWS_HOTSPOTS_CONFIG_DIR")
            os.environ["NEWS_HOTSPOTS_DEFAULTS_DIR"] = defaults_dir
            os.environ["NEWS_HOTSPOTS_CONFIG_DIR"] = config_dir
            try:
                self.assertEqual(topic_utils.get_topic_priority_list(), ["business", "social"])
                self.assertEqual(topic_utils.normalize_topic_id("old"), "social")
            finally:
                topic_utils.load_default_topic_rules.cache_clear()
                if old_defaults is None:
                    os.environ.pop("NEWS_HOTSPOTS_DEFAULTS_DIR", None)
                else:
                    os.environ["NEWS_HOTSPOTS_DEFAULTS_DIR"] = old_defaults
                if old_config is None:
                    os.environ.pop("NEWS_HOTSPOTS_CONFIG_DIR", None)
                else:
                    os.environ["NEWS_HOTSPOTS_CONFIG_DIR"] = old_config


if __name__ == "__main__":
    unittest.main()
