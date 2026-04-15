#!/usr/bin/env bash
# Automatically generate a labeled dataset by running all scripted tests
# and several normal idle periods, then compute evaluation metrics.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

DATA_DIR="$PROJECT_ROOT/data"
TRACE_FILE="$PROJECT_ROOT/tracing/combined_trace.bt"
HID_MONITOR="$PROJECT_ROOT/tracing/hid_provenance_monitor.sh"

# How long to trace each run (seconds)
TRACE_DURATION="${TRACE_DURATION:-8}"
# How many normal (idle) runs to create
NORMAL_RUNS="${NORMAL_RUNS:-5}"

mkdir -p "$DATA_DIR/normal" "$DATA_DIR/scripted"

echo "========================================"
echo "HID Behavior Detector - Dataset Generator"
echo "========================================"
echo "Trace duration per run: ${TRACE_DURATION}s"
echo "Normal idle runs: ${NORMAL_RUNS}"
echo ""

run_trace() {
    local run_type="$1"
    local test_script="${2:-}"
    local timestamp
    timestamp=$(date +%Y-%m-%d_%H-%M-%S)
    
    local output_dir="$DATA_DIR/$run_type"
    local output_file="$output_dir/${run_type}_${timestamp}.jsonl"
    local hid_file="$output_dir/${run_type}_${timestamp}_hid.jsonl"
    
    echo "  Output: $output_file"
    
    # Start HID monitor
    sudo env TRUSTED_HID_PAIRS="${TRUSTED_HID_PAIRS:-}" \
      bash "$HID_MONITOR" > "$hid_file" 2>/dev/null &
    local hid_pid=$!
    
    # Start bpftrace
    sudo timeout "${TRACE_DURATION}s" bpftrace "$TRACE_FILE" > "$output_file" 2>/dev/null &
    local trace_pid=$!
    
    # Give tracing a moment to initialize
    sleep 1
    
    # If scripted, run the test payload
    if [[ -n "$test_script" && -f "$test_script" ]]; then
        bash "$test_script" >/dev/null 2>&1 || true
    fi
    
    # Wait for trace to complete (timeout handles duration)
    wait "$trace_pid" 2>/dev/null || true
    
    # Stop HID monitor
    sudo kill "$hid_pid" 2>/dev/null || true
    wait "$hid_pid" 2>/dev/null || true
    
    # Brief pause between runs
    sleep 1
}

# Collect all scripted test files
mapfile -t SCRIPTED_TESTS < <(find "$SCRIPT_DIR" -maxdepth 1 -name 'scripted_test_*.sh' | sort)

echo "Found ${#SCRIPTED_TESTS[@]} scripted test(s)"
echo ""

# Run scripted tests
echo "=== Running Scripted Tests ==="
for test_script in "${SCRIPTED_TESTS[@]}"; do
    test_name=$(basename "$test_script")
    echo "[$test_name]"
    run_trace "scripted" "$test_script"
done
echo ""

# Run normal (idle) traces
echo "=== Running Normal (Idle) Traces ==="
for i in $(seq 1 "$NORMAL_RUNS"); do
    echo "[normal run $i/$NORMAL_RUNS]"
    run_trace "normal" ""
done
echo ""

# Run batch analysis
echo "=== Running Batch Analysis ==="
bash "$SCRIPT_DIR/batch_analyze.sh"
echo ""

# Run evaluation
echo "=== Evaluation Results ==="
bash "$SCRIPT_DIR/evaluate_summary.sh"
echo ""

# Count results
total_scripted=$(find "$DATA_DIR/scripted" -name '*.jsonl' ! -name '*_hid.jsonl' 2>/dev/null | wc -l)
total_normal=$(find "$DATA_DIR/normal" -name '*.jsonl' ! -name '*_hid.jsonl' 2>/dev/null | wc -l)

echo "========================================"
echo "Dataset generation complete!"
echo "  Scripted samples: $total_scripted"
echo "  Normal samples:   $total_normal"
echo "  Total:            $((total_scripted + total_normal))"
echo ""
echo "Results saved to: $PROJECT_ROOT/results/summary.tsv"
echo "========================================"
