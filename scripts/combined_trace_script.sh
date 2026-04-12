#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TRACE_FILE="$PROJECT_ROOT/tracing/combined_trace.bt"
DATA_DIR="$PROJECT_ROOT/data"

echo "Enter run type (normal or scripted):"
read -r RUN_TYPE

if [[ "$RUN_TYPE" != "normal" && "$RUN_TYPE" != "scripted" ]]; then
    echo "Invalid run type. Use 'normal' or 'scripted'."
    exit 1
fi

OUTPUT_DIR="$DATA_DIR/$RUN_TYPE"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUTPUT_FILE="$OUTPUT_DIR/${RUN_TYPE}_${TIMESTAMP}.jsonl"
HID_OUTPUT_FILE="$OUTPUT_DIR/${RUN_TYPE}_${TIMESTAMP}_hid.jsonl"

echo "Saving trace to: $OUTPUT_FILE"
echo "Saving HID provenance to: $HID_OUTPUT_FILE"
sudo bash "$PROJECT_ROOT/tracing/hid_provenance_monitor.sh" > "$HID_OUTPUT_FILE" &
HID_PID=$!

cleanup() {
    sudo kill "$HID_PID" 2>/dev/null || true
}
trap cleanup EXIT

sudo bpftrace "$TRACE_FILE" > "$OUTPUT_FILE"
