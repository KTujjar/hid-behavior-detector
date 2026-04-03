# HID Behavior Detector

OS-level behavioral detection pipeline for suspicious command execution patterns and potential HID-triggered attacks.

This project captures low-level system telemetry, extracts behavioral features, and scores each run as suspicious or not suspicious.

## What this project does

- Captures Linux OS events with `bpftrace`:
  - process execution (`exec`)
  - process forking (`fork`)
  - network connect syscalls (`connect`)
- Captures HID input-device provenance with `udevadm`:
  - input device attach/remove actions
  - device metadata (vendor/product IDs, serial, dev path)
  - keyboard indicator and trust flag
- Merges event streams into a single timeline.
- Computes behavior features (bursting, timing, process tree depth, HID-to-shell correlation).
- Produces a scored report with human-readable reasons.

## Architecture

- `tracing/`
  - `exec_trace.bt`, `fork_trace.bt`, `connect_trace.bt`: bpftrace probes
  - `combined_trace.bt`: combined probe script
  - `hid_provenance_monitor.sh`: HID provenance collector from udev events
- `scripts/`
  - `collect_trace.sh`: records `exec/fork/connect/hid` into a timestamped trace directory
  - `analyze_trace_dir.sh`: analyzes one trace directory
  - `combined_trace_script.sh`: single combined trace + HID sidecar capture
  - `batch_analyze.sh`: batch analysis for normal/scripted datasets
  - `evaluate_summary.sh`: computes TP/TN/FP/FN from summary output
- `analyzer/`
  - C++ analyzer executable (`hid-analyzer`) for parsing, feature extraction, scoring, and report generation

## Features used for detection

The analyzer currently scores these types of indicators:

- shell-like command execution seen (`bash`, `sh`, etc.)
- high exec burst inside a 1-second sliding window
- network connect shortly after first shell execution
- deep process tree
- interpreter/network tool shortly after shell-like execution
- untrusted keyboard attach events
- shell execution soon after HID attach

The detector returns:

- `Suspicion score: <int>`
- `Suspicious: yes|no`
- `Reasons:` with weighted evidence strings

## Prerequisites

### Runtime collection (Linux)

- Linux host or Linux VM
- `bpftrace`
- `udevadm` (from `udev`)
- `sudo` access

### Analyzer build

- CMake 3.16+
- C++17 compiler
  - GCC/Clang on Linux
  - MSVC on Windows

## Build the analyzer

From repository root:

```bash
cd analyzer
cmake -S . -B build
cmake --build build
```

Built binary path examples:

- Linux: `analyzer/build/hid-analyzer`
- Windows (MSVC): `analyzer/build/Debug/hid-analyzer.exe`

## Desktop interface (Linux)

A simple desktop UI is available in `ui/desktop_app.py` and exposes all current workflows:

- start/stop live capture (`collect_trace.sh`)
- run combined trace flow (`normal` / `scripted`)
- analyze one trace directory or arbitrary JSONL files
- run batch analysis + confusion-matrix evaluation
- configure trusted HID allowlist (`TRUSTED_HID_PAIRS`)
- browse/filter generated reports in `results/`

Run:

```bash
python3 ui/desktop_app.py
```

Reference docs for command contracts and UI feature parity:

- `ui/DESKTOP_INTERFACE.md`

## Quick start (recommended end-to-end flow)

1. Start telemetry collection:

```bash
./scripts/collect_trace.sh
```

2. Reproduce a test scenario (normal interaction or scripted payload behavior).
3. Press Enter in the collector terminal to stop capture.
4. Analyze the generated trace directory:

```bash
./scripts/analyze_trace_dir.sh data/trace_<timestamp>
```

5. Open the generated report in `results/`.

## Data files produced by collection

`collect_trace.sh` writes:

- `exec.jsonl`
- `fork.jsonl`
- `connect.jsonl`
- `hid.jsonl`

`analyze_trace_dir.sh` always uses `exec/fork/connect` and auto-includes `hid.jsonl` if present.

## HID provenance and trusted device list

`tracing/hid_provenance_monitor.sh` supports a trusted USB keyboard allowlist via:

```bash
export TRUSTED_HID_PAIRS="046d:c31c,1d6b:0002"
```

Format is lowercase or mixed-case `vendor_id:product_id` pairs, comma-separated.

If a keyboard attach event does not match this list, it is marked untrusted and contributes to score.

## Analyzer CLI usage

```text
hid-analyzer <input.jsonl> [more.jsonl ...]
hid-analyzer --out <report.txt> <input.jsonl> [...]
```

Examples:

```bash
# Analyze one file
./analyzer/build/hid-analyzer data/combined.jsonl

# Merge multiple streams
./analyzer/build/hid-analyzer --out results/run_report.txt \
  data/trace_2026-03-22_16-45-56/exec.jsonl \
  data/trace_2026-03-22_16-45-56/fork.jsonl \
  data/trace_2026-03-22_16-45-56/connect.jsonl \
  data/trace_2026-03-22_16-45-56/hid.jsonl
```

## Batch evaluation workflow

If you have datasets organized under `data/normal` and `data/scripted` (or matching `data/normal_*.jsonl`, `data/scripted_*.jsonl`):

```bash
./scripts/batch_analyze.sh
./scripts/evaluate_summary.sh
```

Outputs:

- `results/summary.tsv`
- per-run reports in `results/`
- confusion-matrix style counts (TP/TN/FP/FN) from `evaluate_summary.sh`

## Event JSON schema (current)

### Process/network events

- `exec`: `ts_ns`, `type`, `pid`, `comm`
- `fork`: `ts_ns`, `type`, `parent_pid`, `child_pid`, `parent_comm`, `child_comm`
- `connect`: `ts_ns`, `type`, `pid`, `comm`

### HID provenance events

- `hid_attach`:
  - `ts_ns`, `type`, `action`, `subsystem`
  - `devnode`, `devpath`
  - `vendor_id`, `product_id`, `serial`
  - `keyboard` (bool)
  - `trusted` (bool)

## Notes and limitations

- Event coverage is Linux-focused today (`bpftrace` + `udev`).
- The detector is currently a weighted rule system, not a trained ML classifier.
- HID provenance captures attach/remove context, not full keystroke content.
- Thresholds are intentionally simple and may require tuning for your environment.

## Suggested next improvements

- Add baseline profiling per host/user to reduce false positives.
- Add optional ETW collector path for Windows parity.
- Add unit tests for parser + detector scoring.
- Add replay tests from saved JSONL fixtures in CI.

