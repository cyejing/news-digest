#!/usr/bin/env python3
"""
Unified data collection pipeline for news-digest.

Runs fetch steps, merges them into an internal JSON inside a debug directory,
then renders a compact summary JSON for downstream prompt-writing flows.
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Optional

SCRIPTS_DIR = Path(__file__).parent
DEFAULT_TIMEOUT = 1800
MERGE_TIMEOUT = 300
SUMMARY_TIMEOUT = 120
DEFAULT_SUMMARY_TOP = 15
STEP_COOLDOWN_DEFAULTS = {
    "fetch-twitter.py": ("BB_BROWSER_TWITTER_COOLDOWN_SECONDS", 7.0),
    "fetch-reddit.py": ("BB_BROWSER_REDDIT_COOLDOWN_SECONDS", 6.0),
    "fetch-google.py": ("BB_BROWSER_GOOGLE_COOLDOWN_SECONDS", 12.0),
    "fetch-v2ex.py": ("BB_BROWSER_V2EX_COOLDOWN_SECONDS", 5.0),
    "fetch-github.py": ("NEWS_DIGEST_GITHUB_COOLDOWN_SECONDS", 2.0),
}


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def count_output_items(output_path: Path) -> int:
    if not output_path.exists() or output_path.suffix != ".json":
        return 0
    try:
        with open(output_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return 0
    return (
        data.get("total_articles")
        or data.get("total_posts")
        or data.get("total_releases")
        or data.get("total_results")
        or data.get("total")
        or data.get("output_stats", {}).get("total_articles")
        or 0
    )


def run_step(
    name: str,
    script: str,
    args_list: list,
    output_path: Optional[Path],
    timeout: int = DEFAULT_TIMEOUT,
    force: bool = False,
    cooldown_s: Optional[float] = None,
    output_flag: str = "--output",
) -> Dict[str, Any]:
    t0 = time.time()
    cmd = [sys.executable, str(SCRIPTS_DIR / script)] + args_list
    if output_path is not None:
        cmd += [output_flag, str(output_path)]
    if force:
        cmd.append("--force")

    try:
        process = subprocess.Popen(
            cmd,
            text=True,
            env=os.environ,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stdout, stderr = process.communicate()
            else:
                process.kill()
                stdout, stderr = process.communicate()
            elapsed = time.time() - t0
            return {
                "name": name,
                "status": "timeout",
                "elapsed_s": round(elapsed, 1),
                "count": 0,
                "effective_timeout_s": timeout,
                "cooldown_s": cooldown_s,
                "stderr_tail": [f"Killed after {timeout}s"],
            }

        elapsed = time.time() - t0
        ok = process.returncode == 0
        count = count_output_items(output_path) if ok and output_path is not None else 0
        return {
            "name": name,
            "status": "ok" if ok else "error",
            "elapsed_s": round(elapsed, 1),
            "count": count,
            "effective_timeout_s": timeout,
            "cooldown_s": cooldown_s,
            "stderr_tail": (stderr or "").strip().split("\n")[-3:] if not ok else [],
        }
    except Exception as exc:
        elapsed = time.time() - t0
        return {
            "name": name,
            "status": "error",
            "elapsed_s": round(elapsed, 1),
            "count": 0,
            "effective_timeout_s": timeout,
            "cooldown_s": cooldown_s,
            "stderr_tail": [str(exc)],
        }


def get_cooldown_for_script(script: str) -> Optional[float]:
    config = STEP_COOLDOWN_DEFAULTS.get(script)
    if not config:
        return None
    env_name, default = config
    try:
        return float(os.environ.get(env_name, str(default)))
    except ValueError:
        return default


def resolve_debug_dir(debug_dir: Optional[Path]) -> Path:
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        return debug_dir
    return Path(tempfile.mkdtemp(prefix="td-pipeline-"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full news-digest pipeline and produce a compact summary output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--defaults", type=Path, default=Path("config/defaults"), help="Skill defaults config dir")
    parser.add_argument("--config", type=Path, default=None, help="User config overlay dir")
    parser.add_argument("--hours", type=int, default=48, help="Time window in hours")
    parser.add_argument("--archive-dir", type=Path, default=None, help="Archive dir for previous summary JSON files")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Required output path for summary.json")
    parser.add_argument("--debug-dir", type=Path, default=None, help="Directory for debug and intermediate files")
    parser.add_argument("--summary-top", type=int, default=DEFAULT_SUMMARY_TOP, help="Top N items per topic in summary output")
    parser.add_argument(
        "--step-timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Per-step timeout in seconds (default: 1800)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--force", action="store_true", help="Force re-fetch ignoring caches")
    parser.add_argument("--skip", type=str, default="", help="Comma-separated list of steps to skip")

    args = parser.parse_args()
    logger = setup_logging(args.verbose)
    skip_steps = {item.strip().lower() for item in args.skip.split(",") if item.strip()}

    debug_dir = resolve_debug_dir(args.debug_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary_output = args.output
    merged_output = debug_dir / "merged.json"
    meta_output = debug_dir / "pipeline.meta.json"

    tmp_rss = debug_dir / "rss.json"
    tmp_twitter = debug_dir / "twitter.json"
    tmp_google = debug_dir / "google.json"
    tmp_github = debug_dir / "github.json"
    tmp_trending = debug_dir / "trending.json"
    tmp_api = debug_dir / "api.json"
    tmp_v2ex = debug_dir / "v2ex.json"
    tmp_reddit = debug_dir / "reddit.json"

    logger.info("📁 Debug directory: %s", debug_dir)
    logger.info("📝 Summary JSON output: %s", summary_output)

    common = ["--defaults", str(args.defaults)]
    if args.config:
        common += ["--config", str(args.config)]
    common += ["--hours", str(args.hours)]
    verbose_flag = ["--verbose"] if args.verbose else []

    steps = [
        ("rss", "RSS", "fetch-rss.py", common + verbose_flag, tmp_rss, None),
        ("twitter", "Twitter", "fetch-twitter.py", common + verbose_flag, tmp_twitter, get_cooldown_for_script("fetch-twitter.py")),
        ("google", "Google News", "fetch-google.py", common + verbose_flag, tmp_google, get_cooldown_for_script("fetch-google.py")),
        ("github", "GitHub", "fetch-github.py", common + verbose_flag, tmp_github, get_cooldown_for_script("fetch-github.py")),
        (
            "trending",
            "GitHub Trending",
            "fetch-github-trending.py",
            ["--hours", str(args.hours), "--defaults", str(args.defaults)]
            + (["--config", str(args.config)] if args.config else [])
            + verbose_flag,
            tmp_trending,
            None,
        ),
        ("api", "API Sources", "fetch-api.py", verbose_flag, tmp_api, None),
        ("v2ex", "V2EX Hot", "fetch-v2ex.py", verbose_flag, tmp_v2ex, get_cooldown_for_script("fetch-v2ex.py")),
        ("reddit", "Reddit", "fetch-reddit.py", common + verbose_flag, tmp_reddit, get_cooldown_for_script("fetch-reddit.py")),
    ]

    active_steps = []
    for step_key, name, script, step_args, out_path, cooldown_s in steps:
        if step_key in skip_steps:
            logger.info("  ⏭️  %s: skipped (--skip)", name)
            continue
        active_steps.append((name, script, step_args, out_path, cooldown_s))

    logger.info("🚀 Starting pipeline: %d/%d sources, %sh window", len(active_steps), len(steps), args.hours)
    t_start = time.time()

    step_results = []
    if active_steps:
        with ThreadPoolExecutor(max_workers=len(active_steps)) as pool:
            futures = {}
            for name, script, step_args, out_path, cooldown_s in active_steps:
                future = pool.submit(
                    run_step,
                    name,
                    script,
                    step_args,
                    out_path,
                    args.step_timeout,
                    args.force,
                    cooldown_s,
                )
                futures[future] = name

            for future in as_completed(futures):
                result = future.result()
                step_results.append(result)
                status_icon = {"ok": "✅", "error": "❌", "timeout": "⏰"}.get(result["status"], "?")
                logger.info("  %s %s: %s items (%ss)", status_icon, result["name"], result["count"], result["elapsed_s"])
                if result["status"] != "ok" and result["stderr_tail"]:
                    for line in result["stderr_tail"]:
                        logger.debug("    %s", line)

    fetch_elapsed = time.time() - t_start
    logger.info("📡 Fetch phase done in %.1fs", fetch_elapsed)

    logger.info("🔀 Merging & scoring...")
    merge_args = ["--verbose"] if args.verbose else []
    for flag, path in [
        ("--rss", tmp_rss),
        ("--twitter", tmp_twitter),
        ("--google", tmp_google),
        ("--github", tmp_github),
        ("--trending", tmp_trending),
        ("--api", tmp_api),
        ("--v2ex", tmp_v2ex),
        ("--reddit", tmp_reddit),
    ]:
        if path.exists():
            merge_args += [flag, str(path)]
    if args.archive_dir:
        merge_args += ["--archive-dir", str(args.archive_dir)]

    merge_result = run_step(
        "Merge",
        "merge-sources.py",
        merge_args,
        merged_output,
        timeout=MERGE_TIMEOUT,
        force=False,
        cooldown_s=None,
    )

    if merge_result["status"] == "ok":
        logger.info("🧾 Rendering summary...")
        summarize_args = [
            "--input", str(merged_output),
            "--top", str(args.summary_top),
        ]
        summary_result = run_step(
            "Summarize",
            "merge-summarize.py",
            summarize_args,
            summary_output,
            timeout=SUMMARY_TIMEOUT,
            force=False,
            cooldown_s=None,
        )
    else:
        summary_result = {
            "name": "Summarize",
            "status": "skipped",
            "elapsed_s": 0,
            "count": 0,
            "effective_timeout_s": SUMMARY_TIMEOUT,
            "cooldown_s": None,
            "stderr_tail": [],
        }

    total_elapsed = time.time() - t_start

    logger.info("%s", "=" * 50)
    logger.info("📊 Pipeline Summary (%.1fs total)", total_elapsed)
    for result in step_results:
        logger.info("   %-14s %-8s %4d items %6.1fs", result["name"], result["status"], result["count"], result["elapsed_s"])
    logger.info("   %-14s %-8s %4d items %6.1fs", "Merge", merge_result.get("status", "?"), merge_result.get("count", 0), merge_result.get("elapsed_s", 0))
    logger.info("   %-14s %-8s %4d items %6.1fs", "Summarize", summary_result.get("status", "?"), summary_result.get("count", 0), summary_result.get("elapsed_s", 0))
    logger.info("   Summary: %s", summary_output)
    logger.info("   Meta: %s", meta_output)
    logger.info("   Debug Dir: %s", debug_dir)

    meta = {
        "pipeline_version": "2.0.0",
        "debug_dir": str(debug_dir),
        "total_elapsed_s": round(total_elapsed, 1),
        "fetch_elapsed_s": round(fetch_elapsed, 1),
        "steps": step_results,
        "merge": merge_result,
        "summary_format": "json",
        "summary_status": summary_result.get("status"),
        "summary_elapsed_s": summary_result.get("elapsed_s"),
        "summary_output": str(summary_output),
    }
    with open(meta_output, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    if merge_result["status"] != "ok":
        logger.error("❌ Merge failed: %s", merge_result["stderr_tail"])
        return 1
    if summary_result["status"] != "ok":
        logger.error("❌ Summary failed: %s", summary_result["stderr_tail"])
        return 1

    logger.info("✅ Done → %s", summary_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
