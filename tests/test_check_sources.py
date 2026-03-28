#!/usr/bin/env python3
"""Tests for check-sources.py."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).parent
MODULE_PATH = TESTS_DIR / "check-sources.py"

spec = importlib.util.spec_from_file_location("check_sources", MODULE_PATH)
check_sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_sources)


class TestCheckSources(unittest.TestCase):
    def test_parse_types_arg_validates_known_values(self):
        self.assertEqual(check_sources.parse_types_arg("rss,github"), ["rss", "github"])
        with self.assertRaises(ValueError):
            check_sources.parse_types_arg("rss,unknown")

    def test_build_execution_list_includes_unsupported_and_api(self):
        merged_sources = [
            {"id": "openai-rss", "name": "OpenAI Blog", "type": "rss", "enabled": True},
            {"id": "sama-twitter", "name": "Sam Altman", "type": "twitter", "enabled": True},
            {"id": "pytorch-github", "name": "PyTorch", "type": "github", "enabled": True},
        ]
        api_sources = [{"id": "weibo-api", "name": "Weibo Hot Search", "topics": ["world-affairs"]}]

        with patch.object(check_sources.config_loader, "load_merged_sources", return_value=merged_sources):
            with patch.object(check_sources.fetch_api, "load_api_sources", return_value=api_sources):
                execution_list = check_sources.build_execution_list(
                    defaults_dir=Path("config/defaults"),
                    config_dir=None,
                    selected_types=["rss", "twitter", "github", "api"],
                    selected_ids=None,
                    include_unsupported=True,
                )

        self.assertEqual(
            [item["id"] for item in execution_list],
            ["openai-rss", "sama-twitter", "pytorch-github", "weibo-api"],
        )
        self.assertEqual(execution_list[-1]["type"], "api")

    def test_build_execution_list_can_skip_unsupported(self):
        merged_sources = [
            {"id": "openai-rss", "name": "OpenAI Blog", "type": "rss", "enabled": True},
            {"id": "sama-twitter", "name": "Sam Altman", "type": "twitter", "enabled": True},
        ]

        with patch.object(check_sources.config_loader, "load_merged_sources", return_value=merged_sources):
            with patch.object(check_sources.fetch_api, "load_api_sources", return_value=[]):
                execution_list = check_sources.build_execution_list(
                    defaults_dir=Path("config/defaults"),
                    config_dir=None,
                    selected_types=["rss", "twitter"],
                    selected_ids=None,
                    include_unsupported=False,
                )

        self.assertEqual([item["id"] for item in execution_list], ["openai-rss"])

    def test_execute_checks_marks_unsupported_without_failing(self):
        execution_list = [{"id": "sama-twitter", "name": "Sam Altman", "type": "twitter"}]
        results, exit_code = check_sources.execute_checks(
            execution_list=execution_list,
            fail_fast=False,
            logger=check_sources.logging.getLogger("test"),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(results[0]["status"], "unsupported")

    def test_execute_checks_fail_fast_stops_after_first_error(self):
        execution_list = [
            {"id": "openai-rss", "name": "OpenAI Blog", "type": "rss"},
            {"id": "pytorch-github", "name": "PyTorch", "type": "github"},
        ]

        with patch.object(check_sources.fetch_rss, "_get_rss_cache", return_value={}):
            with patch.object(check_sources.fetch_rss, "_flush_rss_cache", return_value=None):
                with patch.object(check_sources.fetch_github, "resolve_github_token", return_value=None):
                    with patch.object(check_sources.fetch_github, "_get_github_cache", return_value={}):
                        with patch.object(check_sources.fetch_github, "_flush_github_cache", return_value=None):
                            with patch.object(
                                check_sources,
                                "check_rss_source",
                                return_value={
                                    "source_id": "openai-rss",
                                    "source_type": "rss",
                                    "name": "OpenAI Blog",
                                    "status": "error",
                                    "count": 0,
                                    "error": "boom",
                                    "elapsed_s": 0.1,
                                    "attempts": 1,
                                    "unsupported_reason": None,
                                },
                            ):
                                with patch.object(check_sources, "check_github_source") as check_github_source:
                                    results, exit_code = check_sources.execute_checks(
                                        execution_list=execution_list,
                                        fail_fast=True,
                                        logger=check_sources.logging.getLogger("test"),
                                    )

        self.assertEqual(exit_code, 1)
        self.assertEqual(len(results), 1)
        check_github_source.assert_not_called()

    def test_write_report_persists_results(self):
        results = [
            {
                "source_id": "openai-rss",
                "source_type": "rss",
                "name": "OpenAI Blog",
                "status": "ok",
                "count": 3,
                "error": None,
                "elapsed_s": 0.2,
                "attempts": 1,
                "unsupported_reason": None,
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            check_sources.write_report(
                output_path=output_path,
                results=results,
                defaults_dir=Path("config/defaults"),
                config_dir=None,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["results"][0]["source_id"], "openai-rss")
        self.assertEqual(payload["filters"]["cache"], "disabled")

    def test_mark_empty_as_error_converts_zero_count(self):
        result = check_sources.mark_empty_as_error(
            {
                "source_id": "openai-rss",
                "source_type": "rss",
                "name": "OpenAI Blog",
                "status": "ok",
                "count": 0,
                "error": None,
                "elapsed_s": 0.2,
                "attempts": 1,
                "unsupported_reason": None,
            }
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "parsed 0 items")

    def test_main_types_api_only_uses_api_sources(self):
        api_sources = [{"id": "weibo-api", "name": "Weibo Hot Search", "topics": ["world-affairs"]}]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            with patch.object(check_sources.config_loader, "load_merged_sources", return_value=[]):
                with patch.object(check_sources.fetch_api, "load_api_sources", return_value=api_sources):
                    with patch.object(
                        check_sources,
                        "execute_checks",
                        return_value=(
                            [
                                {
                                    "source_id": "weibo-api",
                                    "source_type": "api",
                                    "name": "Weibo Hot Search",
                                    "status": "ok",
                                    "count": 5,
                                    "error": None,
                                    "elapsed_s": 0.1,
                                    "attempts": None,
                                    "unsupported_reason": None,
                                }
                            ],
                            0,
                        ),
                    ) as execute_checks:
                        exit_code = check_sources.main(
                            ["--types", "api", "--output", str(output_path)]
                        )

        self.assertEqual(exit_code, 0)
        execution_list = execute_checks.call_args.kwargs["execution_list"]
        self.assertEqual([item["id"] for item in execution_list], ["weibo-api"])


if __name__ == "__main__":
    unittest.main()
