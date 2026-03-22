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

echo "Saving trace to: $OUTPUT_FILE"
sudo bpftrace "$TRACE_FILE" > "$OUTPUT_FILE"
