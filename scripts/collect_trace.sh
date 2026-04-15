#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
OUT_DIR="data/trace_${STAMP}"
mkdir -p "$OUT_DIR"

echo "Writing separate logs to: $OUT_DIR"
sudo bpftrace tracing/exec_trace.bt > "$OUT_DIR/exec.jsonl" &
EXEC_PID=$!
sudo bpftrace tracing/fork_trace.bt > "$OUT_DIR/fork.jsonl" &
FORK_PID=$!
sudo bpftrace tracing/connect_trace.bt > "$OUT_DIR/connect.jsonl" &
CONN_PID=$!
sudo env TRUSTED_HID_PAIRS="${TRUSTED_HID_PAIRS:-}" \
  bash "$PROJECT_ROOT/tracing/hid_provenance_monitor.sh" > "$OUT_DIR/hid.jsonl" &
HID_PID=$!

echo "Tracing started (exec pid=$EXEC_PID fork=$FORK_PID connect=$CONN_PID hid=$HID_PID)."
echo "Press Enter to stop."
read -r

sudo kill "$EXEC_PID" "$FORK_PID" "$CONN_PID" "$HID_PID" 2>/dev/null || true
wait || true
echo "Saved: $OUT_DIR/exec.jsonl $OUT_DIR/fork.jsonl $OUT_DIR/connect.jsonl $OUT_DIR/hid.jsonl"
