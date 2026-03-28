#!/usr/bin/env python3
"""
Sequential per-source diagnostics for news-digest.

Checks each implemented source one-by-one and prints live console output:
RSS and GitHub sources come from sources.json, API sources use the built-in
source list from fetch-api.py. Unsupported source types are reported but do
not fail the command.

Usage:
    uv run scripts/check-sources.py --defaults config/defaults
"""

import argparse
import importlib.util
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SUPPORTED_TYPES = ("rss", "github", "api")
ORDERED_TYPES = ("rss", "twitter", "github", "reddit", "api")
UNFILTERED_CUTOFF = datetime(1970, 1, 1, tzinfo=timezone.utc)


def load_script_module(module_name: str, script_name: str):
    script_path = SCRIPTS_DIR / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load script module: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_rss = load_script_module("check_sources_fetch_rss", "fetch-rss.py")
fetch_github = load_script_module("check_sources_fetch_github", "fetch-github.py")
fetch_api = load_script_module("check_sources_fetch_api", "fetch-api.py")
config_loader = load_script_module("check_sources_config_loader", "config_loader.py")


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def parse_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_types_arg(value: str) -> List[str]:
    requested = parse_csv(value)
    if not requested:
        return list(ORDERED_TYPES)

    invalid = [item for item in requested if item not in ORDERED_TYPES]
    if invalid:
        raise ValueError(
            f"Unsupported source types: {', '.join(invalid)}. "
            f"Valid types: {', '.join(ORDERED_TYPES)}"
        )
    return requested


def filter_sources(
    sources: Sequence[Dict[str, Any]],
    selected_ids: Optional[set],
    selected_types: Sequence[str],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    selected_type_set = set(selected_types)
    for source in sources:
        source_id = source.get("id")
        source_type = source.get("type")
        if source_type not in selected_type_set:
            continue
        if selected_ids and source_id not in selected_ids:
            continue
        filtered.append(source)
    return filtered


def normalize_result(
    source: Dict[str, Any],
    result: Dict[str, Any],
    elapsed_s: float,
    override_status: Optional[str] = None,
    unsupported_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "source_id": source.get("id"),
        "source_type": source.get("type"),
        "name": source.get("name", source.get("id", "unknown")),
        "status": override_status or result.get("status", "error"),
        "count": int(result.get("count", 0) or 0),
        "error": result.get("error"),
        "elapsed_s": round(elapsed_s, 1),
        "attempts": result.get("attempts"),
        "unsupported_reason": unsupported_reason,
    }


def mark_empty_as_error(result: Dict[str, Any]) -> Dict[str, Any]:
    if result["status"] == "ok" and result["count"] == 0:
        updated = result.copy()
        updated["status"] = "error"
        updated["error"] = "parsed 0 items"
        return updated
    return result


def make_unsupported_result(source: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return normalize_result(
        source,
        result={},
        elapsed_s=0.0,
        override_status="unsupported",
        unsupported_reason=reason,
    )


def describe_source(source: Dict[str, Any]) -> str:
    return f"{source.get('type')}/{source.get('id')} {source.get('name', source.get('id', 'unknown'))}"


def print_start(index: int, total: int, source: Dict[str, Any]) -> None:
    print(f"[{index}/{total}] checking {describe_source(source)}", flush=True)


def print_result(result: Dict[str, Any]) -> None:
    descriptor = f"{result['source_type']}/{result['source_id']} {result['name']}"
    if result["status"] == "ok":
        print(f"✅ {descriptor} ({result['count']} items, {result['elapsed_s']:.1f}s)", flush=True)
    elif result["status"] == "unsupported":
        print(f"⚪ {descriptor} - {result.get('unsupported_reason') or 'unsupported'}", flush=True)
    else:
        error = result.get("error") or "unknown error"
        print(f"❌ {descriptor} - {error}", flush=True)


def build_execution_list(
    defaults_dir: Path,
    config_dir: Optional[Path],
    selected_types: Sequence[str],
    selected_ids: Optional[set],
    include_unsupported: bool,
) -> List[Dict[str, Any]]:
    merged_sources = config_loader.load_merged_sources(defaults_dir, config_dir)
    enabled_sources = [source for source in merged_sources if source.get("enabled", True)]
    filtered_sources = filter_sources(enabled_sources, selected_ids, selected_types)

    grouped: Dict[str, List[Dict[str, Any]]] = {source_type: [] for source_type in ORDERED_TYPES}
    for source in filtered_sources:
        grouped.setdefault(source["type"], []).append(source)

    execution_list: List[Dict[str, Any]] = []
    for source_type in ORDERED_TYPES:
        if source_type == "api":
            continue
        if source_type not in selected_types:
            continue
        if source_type in SUPPORTED_TYPES:
            execution_list.extend(grouped.get(source_type, []))
        elif include_unsupported:
            execution_list.extend(grouped.get(source_type, []))

    if "api" in selected_types:
        api_sources = fetch_api.load_api_sources()
        for source in api_sources:
            source = source.copy()
            source["type"] = "api"
            if selected_ids and source.get("id") not in selected_ids:
                continue
            execution_list.append(source)

    return execution_list


def check_rss_source(source: Dict[str, Any], cutoff: datetime, no_cache: bool) -> Dict[str, Any]:
    t0 = time.time()
    result = fetch_rss.fetch_feed_with_retry(source, cutoff, no_cache=no_cache)
    return mark_empty_as_error(normalize_result(source, result, time.time() - t0))


def check_github_source(
    source: Dict[str, Any],
    cutoff: datetime,
    github_token: Optional[str],
    no_cache: bool,
) -> Dict[str, Any]:
    t0 = time.time()
    result = fetch_github.fetch_releases_with_retry(
        source,
        cutoff,
        github_token=github_token,
        no_cache=no_cache,
    )
    return mark_empty_as_error(normalize_result(source, result, time.time() - t0))


def check_api_source(source: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    result = fetch_api.fetch_source(source)
    return mark_empty_as_error(normalize_result(source, result, time.time() - t0))


def execute_checks(
    execution_list: Sequence[Dict[str, Any]],
    fail_fast: bool,
    logger: logging.Logger,
) -> Tuple[List[Dict[str, Any]], int]:
    results: List[Dict[str, Any]] = []
    cutoff = UNFILTERED_CUTOFF
    no_cache = True
    github_token: Optional[str] = None

    if any(source.get("type") == "rss" for source in execution_list):
        fetch_rss._get_rss_cache(no_cache=no_cache)
    if any(source.get("type") == "github" for source in execution_list):
        github_token = fetch_github.resolve_github_token()
        fetch_github._get_github_cache(no_cache)

    exit_code = 0
    total = len(execution_list)

    try:
        for index, source in enumerate(execution_list, start=1):
            print_start(index, total, source)

            source_type = source.get("type")
            if source_type == "rss":
                result = check_rss_source(source, cutoff, no_cache)
            elif source_type == "github":
                result = check_github_source(source, cutoff, github_token, no_cache)
            elif source_type == "api":
                result = check_api_source(source)
            else:
                result = make_unsupported_result(
                    source,
                    reason=f"unsupported source type: {source_type}",
                )

            print_result(result)
            results.append(result)

            if result["status"] == "error":
                exit_code = 1
                if fail_fast:
                    break
    finally:
        if any(source.get("type") == "rss" for source in execution_list):
            try:
                fetch_rss._flush_rss_cache()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                logger.debug("Failed to flush RSS cache: %s", exc)
        if any(source.get("type") == "github" for source in execution_list):
            try:
                fetch_github._flush_github_cache()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                logger.debug("Failed to flush GitHub cache: %s", exc)

    return results, exit_code


def summarize_results(results: Sequence[Dict[str, Any]]) -> str:
    ok_count = sum(1 for result in results if result["status"] == "ok")
    failed_count = sum(1 for result in results if result["status"] == "error")
    unsupported_count = sum(1 for result in results if result["status"] == "unsupported")
    return f"done: {ok_count} ok, {failed_count} failed, {unsupported_count} unsupported"


def write_report(
    output_path: Path,
    results: Sequence[Dict[str, Any]],
    defaults_dir: Path,
    config_dir: Optional[Path],
) -> None:
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "defaults_dir": str(defaults_dir),
        "config_dir": str(config_dir) if config_dir else None,
        "filters": {
            "cache": "disabled",
            "time_window": "disabled",
            "empty_count_is_error": True,
        },
        "results": list(results),
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sequential per-source diagnostics for news-digest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    uv run scripts/check-sources.py --defaults config/defaults
    uv run scripts/check-sources.py --types rss,github --ids openai-rss,pytorch-github
    uv run scripts/check-sources.py --types api --output /tmp/source-check.json
        """,
    )
    parser.add_argument(
        "--defaults",
        type=Path,
        default=Path("config/defaults"),
        help="Default configuration directory (default: config/defaults)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="User configuration directory for overlays (optional)",
    )
    parser.add_argument(
        "--types",
        type=str,
        default="all",
        help="Comma-separated source types to check (default: all)",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default="",
        help="Comma-separated source ids to check",
    )
    parser.add_argument(
        "--include-unsupported",
        dest="include_unsupported",
        action="store_true",
        help="Include unsupported source types in output (default: on)",
    )
    parser.add_argument(
        "--skip-unsupported",
        dest="include_unsupported",
        action="store_false",
        help="Skip unsupported source types from output",
    )
    parser.set_defaults(include_unsupported=True)
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first source failure",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/td-source-check.json"),
        help="Write JSON report to this path (default: /tmp/td-source-check.json)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbose)

    try:
        selected_types = list(ORDERED_TYPES) if args.types == "all" else parse_types_arg(args.types)
        selected_ids = set(parse_csv(args.ids)) or None
        execution_list = build_execution_list(
            args.defaults,
            args.config,
            selected_types,
            selected_ids,
            args.include_unsupported,
        )
    except Exception as exc:
        logger.error("Initialization failed: %s", exc)
        return 2

    logger.info("Starting source checks for %d sources", len(execution_list))

    try:
        results, exit_code = execute_checks(
            execution_list=execution_list,
            fail_fast=args.fail_fast,
            logger=logger,
        )
        write_report(args.output, results, args.defaults, args.config)
    except Exception as exc:
        logger.error("Check failed: %s", exc)
        return 2

    summary = summarize_results(results)
    print(summary, flush=True)
    logger.info("Report written to %s", args.output)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
