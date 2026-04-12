#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/analyzer/build}"
ANALYZER="$BUILD_DIR/hid-analyzer"
RESULTS_DIR="$PROJECT_ROOT/results"
mkdir -p "$RESULTS_DIR"

# Optional --since YYYY-MM-DD flag: skip files whose embedded date is before this.
SINCE_DATE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --since) SINCE_DATE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [[ -n "$SINCE_DATE" ]]; then
  echo "Filtering: only runs on or after $SINCE_DATE"
fi

if [[ ! -x "$ANALYZER" ]]; then
  echo "Build the analyzer first, e.g.:"
  echo "  cd analyzer && cmake -S . -B build && cmake --build build"
  exit 1
fi

# Extract YYYY-MM-DD from filenames like normal_2026-04-12_16-56-13.jsonl.
# Falls back to the file's mtime if no date is embedded in the name.
file_date() {
  local base
  base="$(basename "$1")"
  if [[ "$base" =~ _([0-9]{4}-[0-9]{2}-[0-9]{2})_ ]]; then
    echo "${BASH_REMATCH[1]}"
  else
    date -r "$1" +%Y-%m-%d 2>/dev/null || echo "0000-00-00"
  fi
}

SUMMARY="$RESULTS_DIR/summary.tsv"
echo -e "run\ttype\tscore\tflagged" > "$SUMMARY"

analyze_file() {
  local f="$1"
  local kind="$2"

  if [[ -n "$SINCE_DATE" ]]; then
    local fdate
    fdate="$(file_date "$f")"
    if [[ "$fdate" < "$SINCE_DATE" ]]; then
      echo "Skipping $f (run date $fdate is before $SINCE_DATE)"
      return
    fi
  fi

  local base
  base="$(basename "$f" .jsonl)"
  local rep="$RESULTS_DIR/${base}_report.txt"
  local hid_sidecar="${f%.jsonl}_hid.jsonl"
  if [[ -f "$hid_sidecar" ]]; then
    "$ANALYZER" --out "$rep" "$f" "$hid_sidecar" >/dev/null
  else
    "$ANALYZER" --out "$rep" "$f" >/dev/null
  fi
  local score flagged
  score="$(grep -E '^Suspicion score:' "$rep" | awk '{print $3}')"
  flagged="$(grep -E '^Suspicious:' "$rep" | awk '{print $2}')"
  echo -e "${base}\t${kind}\t${score}\t${flagged}" >> "$SUMMARY"
  echo "$f -> score=$score suspicious=$flagged"
}

shopt -s nullglob
for f in "$PROJECT_ROOT/data/normal/"*.jsonl; do
  [[ "$f" == *_hid.jsonl ]] && continue
  analyze_file "$f" "normal"
done
for f in "$PROJECT_ROOT/data/scripted/"*.jsonl; do
  [[ "$f" == *_hid.jsonl ]] && continue
  analyze_file "$f" "scripted"
done
for f in "$PROJECT_ROOT/data/normal_"*.jsonl; do
  [[ "$f" == *_hid.jsonl ]] && continue
  analyze_file "$f" "normal"
done
for f in "$PROJECT_ROOT/data/scripted_"*.jsonl; do
  [[ "$f" == *_hid.jsonl ]] && continue
  analyze_file "$f" "scripted"
done

echo "Summary table: $SUMMARY"
