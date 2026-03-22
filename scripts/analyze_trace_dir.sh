#!/usr/bin/env bash
# Analyze a directory produced by collect_trace.sh (exec.jsonl, fork.jsonl, connect.jsonl).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/analyzer/build}"
ANALYZER="$BUILD_DIR/hid-analyzer"

DIR="${1:?usage: analyze_trace_dir.sh /path/to/data/trace_TIMESTAMP}"

if [[ ! -x "$ANALYZER" ]]; then
  echo "Build the analyzer first: cd analyzer && cmake -S . -B build && cmake --build build"
  exit 1
fi

BASE="$(basename "$DIR")"
OUT="$PROJECT_ROOT/results/${BASE}_merged_report.txt"
mkdir -p "$PROJECT_ROOT/results"

"$ANALYZER" --out "$OUT" "$DIR/exec.jsonl" "$DIR/fork.jsonl" "$DIR/connect.jsonl"
echo "Wrote $OUT"
