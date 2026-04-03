# Desktop Interface Design

This document captures the implemented command contracts, screen wireframes, parser behavior, and feature-parity checklist for the Linux desktop UI.

## Chosen Stack

- Runtime: Python 3
- GUI: Tkinter (`tkinter`, `ttk`)
- Reason: no external GUI dependencies, good Linux support, straightforward subprocess/log integration.

## Command Adapter Contracts

Implemented in `ui/workflows.py` with `CommandSpec` and `WorkflowAdapter`.

- `collect_trace()`
  - command: `bash scripts/collect_trace.sh`
  - behavior: long-running; stop by sending newline to stdin.
- `combined_trace(run_type)`
  - command: `bash scripts/combined_trace_script.sh`
  - input: `normal` or `scripted` passed on stdin.
  - behavior: long-running until terminated.
- `analyze_trace_dir(trace_dir)`
  - command: `bash scripts/analyze_trace_dir.sh <trace_dir>`
- `analyze_files(files, out_path)`
  - command: `analyzer/build/hid-analyzer [--out <out_path>] <file1> ...`
- `batch_analyze()`
  - command: `bash scripts/batch_analyze.sh`
- `evaluate_summary(summary_path=None)`
  - command: `bash scripts/evaluate_summary.sh [summary_path]`

All commands inherit environment with optional `TRUSTED_HID_PAIRS`.

## Screen Wireframes (Implemented Tabs)

- **Run Capture**
  - Start/Stop `collect_trace.sh`
  - Start/Stop `combined_trace_script.sh` with run type selector
  - live process output log
- **Single Analysis**
  - mode selector: trace dir vs JSONL files
  - trace directory picker
  - multi-file JSONL picker
  - report output path selector
  - process output + parsed report panel
- **Batch Evaluation**
  - run batch then evaluator sequence
  - summary table (`run`, `type`, `score`, `flagged`)
  - TP/TN/FP/FN metrics display
  - combined logs view
- **Trusted HID**
  - trusted pair editor (`vendor:product`, comma/newline separated)
  - validation + save/apply
  - persistence in `.hid_desktop_ui.json`
- **Reports**
  - list recent `results/*_report.txt`
  - filters: suspicious flag and minimum score
  - raw report viewer

## Parser Specifications

Implemented in `ui/parsers.py`.

- `parse_report_text(...)`
  - key/value parsing from report lines (`<key>: <value>`)
  - reason extraction from `Reasons:` block
  - tolerant to minor format deviations.
- `parse_summary_tsv(...)`
  - tab-separated parsing with header support
  - returns normalized row dictionaries.
- `parse_evaluation_stdout(...)`
  - regex extraction for TP/TN/FP/FN from evaluator output
  - defaults each metric to `0` if not present.

## Feature Parity Checklist

- [x] Start/stop live telemetry capture (`collect_trace.sh`)
- [x] Combined trace workflow with run type input (`combined_trace_script.sh`)
- [x] Analyze trace directory (`analyze_trace_dir.sh`)
- [x] Analyze arbitrary JSONL files (direct analyzer CLI)
- [x] Batch analysis (`batch_analyze.sh`)
- [x] Evaluation metrics (`evaluate_summary.sh`)
- [x] Trusted HID allowlist configuration (`TRUSTED_HID_PAIRS`)
- [x] Full report display with reasons and score/suspicious fields
