#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="/tmp/news-digest"
DEBUG_DIR="$TMP_DIR/debug"

DEFAULTS_DIR="$ROOT_DIR/config/defaults"
DEFAULT_CONFIG_DIR="$ROOT_DIR/workspace/config"
DEFAULT_ARCHIVE_JSON_DIR="$ROOT_DIR/workspace/archive/news-digest/json"

SUMMARY_JSON="$TMP_DIR/summary.json"
MERGED_JSON="$TMP_DIR/merged.json"
SOURCE_CHECK_JSON="$TMP_DIR/source-check.json"
RSS_JSON="$TMP_DIR/rss.json"
GITHUB_JSON="$TMP_DIR/github.json"
TRENDING_JSON="$TMP_DIR/trending.json"
API_JSON="$TMP_DIR/api.json"
TWITTER_JSON="$TMP_DIR/twitter.json"
REDDIT_JSON="$TMP_DIR/reddit.json"
V2EX_JSON="$TMP_DIR/v2ex.json"
GOOGLE_JSON="$TMP_DIR/google.json"

HOURS=48
CONFIG_DIR=""
VERBOSE=false
FORCE=false
SKIP_STEPS=""
CHECK_IDS=""
CHECK_TYPES=""
UNIT_MODULES=""

usage() {
  cat <<'HELP'
Unified maintainer test entrypoint for news-digest.

USAGE:
  ./scripts/test-news-digest.sh full [--hours N] [--config DIR] [--verbose] [--force] [--skip a,b]
  ./scripts/test-news-digest.sh step <rss|github|trending|api|twitter|reddit|v2ex|google|merge|summarize|validate> [--hours N] [--config DIR] [--verbose] [--force]
  ./scripts/test-news-digest.sh check [--ids a,b] [--types rss,github,api] [--verbose]
  ./scripts/test-news-digest.sh unit [tests.test_summarize tests.test_merge ...]

OUTPUTS:
  /tmp/news-digest/summary.json
  /tmp/news-digest/debug/pipeline.meta.json
  /tmp/news-digest/rss.json
  /tmp/news-digest/github.json
  /tmp/news-digest/trending.json
  /tmp/news-digest/api.json
  /tmp/news-digest/twitter.json
  /tmp/news-digest/reddit.json
  /tmp/news-digest/v2ex.json
  /tmp/news-digest/google.json
  /tmp/news-digest/merged.json
  /tmp/news-digest/source-check.json
HELP
}

clean_tmp_dir() {
  rm -rf "$TMP_DIR"
  mkdir -p "$TMP_DIR" "$DEBUG_DIR"
}

bool_flag() {
  local flag_name="$1"
  local enabled="$2"
  if [ "$enabled" = true ]; then
    printf '%s\n' "$flag_name"
  fi
}

config_args() {
  if [ -n "$CONFIG_DIR" ] && [ -d "$CONFIG_DIR" ]; then
    printf -- '--config\n%s\n' "$CONFIG_DIR"
  fi
}

run_cmd() {
  echo "+ $*"
  "$@"
}

parse_common_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --hours) HOURS="$2"; shift 2 ;;
      --config) CONFIG_DIR="$2"; shift 2 ;;
      --verbose|-v) VERBOSE=true; shift ;;
      --force) FORCE=true; shift ;;
      --skip) SKIP_STEPS="$2"; shift 2 ;;
      --ids) CHECK_IDS="$2"; shift 2 ;;
      --types) CHECK_TYPES="$2"; shift 2 ;;
      --help|-h) usage; exit 0 ;;
      *)
        if [ -z "$UNIT_MODULES" ]; then
          UNIT_MODULES="$1"
        else
          UNIT_MODULES="$UNIT_MODULES $1"
        fi
        shift
        ;;
    esac
  done
}

run_full() {
  clean_tmp_dir
  local cmd=(
    uv run "$SCRIPT_DIR/run-pipeline.py"
    --defaults "$DEFAULTS_DIR"
    --hours "$HOURS"
    --archive-dir "$DEFAULT_ARCHIVE_JSON_DIR"
    --output "$SUMMARY_JSON"
    --debug-dir "$DEBUG_DIR"
  )
  if [ -n "$CONFIG_DIR" ] && [ -d "$CONFIG_DIR" ]; then
    cmd+=(--config "$CONFIG_DIR")
  fi
  if [ "$VERBOSE" = true ]; then
    cmd+=(--verbose)
  fi
  if [ "$FORCE" = true ]; then
    cmd+=(--force)
  fi
  if [ -n "$SKIP_STEPS" ]; then
    cmd+=(--skip "$SKIP_STEPS")
  fi
  run_cmd "${cmd[@]}"
}

run_fetch_step() {
  local name="$1"
  shift
  local output_path="$1"
  shift

  mkdir -p "$TMP_DIR"
  local cmd=(uv run "$@")
  run_cmd "${cmd[@]}"
  [ -f "$output_path" ] || { echo "Missing output: $output_path" >&2; exit 1; }
}

run_step() {
  local step="$1"
  shift
  mkdir -p "$TMP_DIR" "$DEBUG_DIR"

  case "$step" in
    validate)
      local cmd=(uv run "$SCRIPT_DIR/validate-config.py" --defaults "$DEFAULTS_DIR")
      if [ -n "$CONFIG_DIR" ] && [ -d "$CONFIG_DIR" ]; then
        cmd+=(--config "$CONFIG_DIR")
      fi
      if [ "$VERBOSE" = true ]; then
        cmd+=(--verbose)
      fi
      run_cmd "${cmd[@]}"
      ;;
    rss)
      run_fetch_step "$step" "$RSS_JSON" "$SCRIPT_DIR/fetch-rss.py" --defaults "$DEFAULTS_DIR" $(config_args) --hours "$HOURS" --output "$RSS_JSON" $(bool_flag --verbose "$VERBOSE") $(bool_flag --force "$FORCE")
      ;;
    github)
      run_fetch_step "$step" "$GITHUB_JSON" "$SCRIPT_DIR/fetch-github.py" --defaults "$DEFAULTS_DIR" $(config_args) --hours "$HOURS" --output "$GITHUB_JSON" $(bool_flag --verbose "$VERBOSE") $(bool_flag --force "$FORCE")
      ;;
    trending)
      run_fetch_step "$step" "$TRENDING_JSON" "$SCRIPT_DIR/fetch-github-trending.py" --defaults "$DEFAULTS_DIR" $(config_args) --hours "$HOURS" --output "$TRENDING_JSON" $(bool_flag --verbose "$VERBOSE") $(bool_flag --force "$FORCE")
      ;;
    api)
      run_fetch_step "$step" "$API_JSON" "$SCRIPT_DIR/fetch-api.py" --output "$API_JSON" $(bool_flag --verbose "$VERBOSE")
      ;;
    twitter)
      run_fetch_step "$step" "$TWITTER_JSON" "$SCRIPT_DIR/fetch-twitter.py" --defaults "$DEFAULTS_DIR" $(config_args) --hours "$HOURS" --output "$TWITTER_JSON" $(bool_flag --verbose "$VERBOSE") $(bool_flag --force "$FORCE")
      ;;
    reddit)
      run_fetch_step "$step" "$REDDIT_JSON" "$SCRIPT_DIR/fetch-reddit.py" --defaults "$DEFAULTS_DIR" $(config_args) --hours "$HOURS" --output "$REDDIT_JSON" $(bool_flag --verbose "$VERBOSE") $(bool_flag --force "$FORCE")
      ;;
    v2ex)
      run_fetch_step "$step" "$V2EX_JSON" "$SCRIPT_DIR/fetch-v2ex.py" --output "$V2EX_JSON" $(bool_flag --verbose "$VERBOSE") $(bool_flag --force "$FORCE")
      ;;
    google)
      run_fetch_step "$step" "$GOOGLE_JSON" "$SCRIPT_DIR/fetch-google.py" --defaults "$DEFAULTS_DIR" $(config_args) --hours "$HOURS" --output "$GOOGLE_JSON" $(bool_flag --verbose "$VERBOSE") $(bool_flag --force "$FORCE")
      ;;
    merge)
      local cmd=(uv run "$SCRIPT_DIR/merge-sources.py" --output "$MERGED_JSON" --archive-dir "$DEFAULT_ARCHIVE_JSON_DIR")
      for pair in \
        "--rss:$RSS_JSON" \
        "--github:$GITHUB_JSON" \
        "--trending:$TRENDING_JSON" \
        "--api:$API_JSON" \
        "--twitter:$TWITTER_JSON" \
        "--reddit:$REDDIT_JSON" \
        "--v2ex:$V2EX_JSON" \
        "--google:$GOOGLE_JSON"; do
        local flag="${pair%%:*}"
        local path="${pair#*:}"
        if [ -f "$path" ]; then
          cmd+=("$flag" "$path")
        fi
      done
      if [ "$VERBOSE" = true ]; then
        cmd+=(--verbose)
      fi
      run_cmd "${cmd[@]}"
      [ -f "$MERGED_JSON" ] || { echo "Missing output: $MERGED_JSON" >&2; exit 1; }
      ;;
    summarize)
      [ -f "$MERGED_JSON" ] || { echo "Missing input: $MERGED_JSON" >&2; exit 1; }
      local cmd=(uv run "$SCRIPT_DIR/merge-summarize.py" --input "$MERGED_JSON" --output "$SUMMARY_JSON" --top 15)
      run_cmd "${cmd[@]}"
      [ -f "$SUMMARY_JSON" ] || { echo "Missing output: $SUMMARY_JSON" >&2; exit 1; }
      ;;
    *)
      echo "Unknown step: $step" >&2
      exit 1
      ;;
  esac
}

run_check() {
  mkdir -p "$TMP_DIR"
  local cmd=(uv run "$ROOT_DIR/tests/check-sources.py" --defaults "$DEFAULTS_DIR" --output "$SOURCE_CHECK_JSON")
  if [ -n "$CONFIG_DIR" ] && [ -d "$CONFIG_DIR" ]; then
    cmd+=(--config "$CONFIG_DIR")
  fi
  if [ -n "$CHECK_IDS" ]; then
    cmd+=(--ids "$CHECK_IDS")
  fi
  if [ -n "$CHECK_TYPES" ]; then
    cmd+=(--types "$CHECK_TYPES")
  fi
  if [ "$VERBOSE" = true ]; then
    cmd+=(--verbose)
  fi
  run_cmd "${cmd[@]}"
}

run_unit() {
  local modules=(
    tests.test_summarize
    tests.test_merge
    tests.test_config
  )
  if [ -n "$UNIT_MODULES" ]; then
    # shellcheck disable=SC2206
    modules=($UNIT_MODULES)
  fi
  run_cmd uv run python -m unittest "${modules[@]}"
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 1
  fi

  local mode="$1"
  shift

  case "$mode" in
    full)
      parse_common_args "$@"
      run_full
      ;;
    step)
      if [ $# -lt 1 ]; then
        usage
        exit 1
      fi
      local step_name="$1"
      shift
      parse_common_args "$@"
      run_step "$step_name"
      ;;
    check)
      parse_common_args "$@"
      run_check
      ;;
    unit)
      parse_common_args "$@"
      run_unit
      ;;
    --help|-h|help)
      usage
      ;;
    *)
      echo "Unknown mode: $mode" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
