#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/analyzer/build}"
ANALYZER="$BUILD_DIR/hid-analyzer"
RESULTS_DIR="$PROJECT_ROOT/results"
mkdir -p "$RESULTS_DIR"

if [[ ! -x "$ANALYZER" ]]; then
  echo "Build the analyzer first, e.g.:"
  echo "  cd analyzer && cmake -S . -B build && cmake --build build"
  exit 1
fi

SUMMARY="$RESULTS_DIR/summary.tsv"
echo -e "run\ttype\tscore\tflagged" > "$SUMMARY"

analyze_file() {
  local f="$1"
  local kind="$2"
  local base
  base="$(basename "$f" .jsonl)"
  local rep="$RESULTS_DIR/${base}_report.txt"
  "$ANALYZER" --out "$rep" "$f" >/dev/null
  local score flagged
  score="$(grep -E '^Suspicion score:' "$rep" | awk '{print $3}')"
  flagged="$(grep -E '^Suspicious:' "$rep" | awk '{print $2}')"
  echo -e "${base}\t${kind}\t${score}\t${flagged}" >> "$SUMMARY"
  echo "$f -> score=$score suspicious=$flagged"
}

shopt -s nullglob
for f in "$PROJECT_ROOT/data/normal/"*.jsonl; do
  analyze_file "$f" "normal"
done
for f in "$PROJECT_ROOT/data/scripted/"*.jsonl; do
  analyze_file "$f" "scripted"
done
for f in "$PROJECT_ROOT/data/normal_"*.jsonl; do
  analyze_file "$f" "normal"
done
for f in "$PROJECT_ROOT/data/scripted_"*.jsonl; do
  analyze_file "$f" "scripted"
done

echo "Summary table: $SUMMARY"
