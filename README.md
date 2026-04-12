# HID Behavior Detector

HID Behavior Detector is a Linux-focused telemetry and detection project for spotting suspicious command execution patterns that may be triggered by newly attached HID devices (especially keyboards).

It combines process activity (`exec`, `fork`, `connect`) with HID provenance events, then scores each run as suspicious or not suspicious with explainable reasons.

## Project overview

The project has three main parts:

- `tracing/`: low-level event collection (`bpftrace` probes + HID monitor via `udevadm`)
- `analyzer/`: C++ detector (`hid-analyzer`) that parses events, extracts features, and writes reports
- `ui/desktop_app.py`: Tkinter desktop app that drives collection, analysis, trusted HID config, and report review

Detection is currently rule-based (weighted scoring), not ML-based.

## What gets detected

The analyzer currently looks for patterns like:

- shell-like process execution
- high burst of exec activity in short windows
- quick network activity after shell start
- deep process trees
- interpreter/network tool usage after shell activity
- untrusted keyboard attach events
- shell activity soon after HID attach

Output includes:

- `Suspicion score: <int>`
- `Suspicious: yes|no`
- `Reasons:` with weighted evidence lines

## Recommended way to use this project: Desktop UI

The easiest way to run the full workflow is through the UI.

### 1) Prerequisites

For full capture workflows, run on Linux (host or VM) with:

- Python 3
- `bpftrace`
- `udevadm` (`udev`)
- `sudo` access
- CMake 3.16+
- C++17 compiler (GCC/Clang on Linux)

On Windows, you can still open the UI, but capture scripts are Linux-only.

### 2) Build the analyzer

From repository root:

```bash
cd analyzer
cmake -S . -B build
cmake --build build
```

Expected binary:

- Linux: `analyzer/build/hid-analyzer`
- Windows (MSVC): `analyzer/build/Debug/hid-analyzer.exe`

### 3) Launch the UI

From repository root:

```bash
python3 ui/desktop_app.py
```

### 4) Use each tab

#### Run Capture tab

Use this tab for live collection:

- **Start Capture** runs `scripts/collect_trace.sh`
- **Stop Capture** ends collection
- **Start Combined Trace** runs `scripts/combined_trace_script.sh` for `normal` or `scripted`

Outputs are written under `data/` and include process/network streams plus HID stream.

#### Single Analysis tab

Use this tab to analyze one run:

- choose **Analyze trace directory** or **Analyze JSONL files**
- set output report path (optional)
- click **Run Analysis**

You get:

- raw process output (left panel)
- parsed report fields and reasons (right panel)

#### Batch Evaluation tab

Use this tab to evaluate many runs:

- optionally set an **Include runs since** filter (Last 7/30/90 days or a custom `YYYY-MM-DD` date) to exclude older files without deleting them
- click **Run Batch + Evaluate**
- this runs `scripts/batch_analyze.sh` then `scripts/evaluate_summary.sh`

You get:

- `results/summary.tsv`
- per-run report files in `results/`
- TP/TN/FP/FN metrics in the UI

> **Note:** Batch Evaluation only picks up files captured with **Start Combined Trace** (stored under `data/normal/` and `data/scripted/`). Captures from **Start Capture** go into timestamped `data/trace_*/` directories and are not included.

#### Trusted HID tab

Use this tab to manage the keyboard allowlist:

**Trusted pairs list** (top section)

- **Add Pair** — opens a dialog to type a `vendor:product` hex pair (e.g. `046d:c31c`)
- **Remove Selected** — removes the highlighted pair from the list instantly
- **Save + Apply** — persists the list to `.hid_desktop_ui.json` and injects it into all future capture/analyze runs via `TRUSTED_HID_PAIRS`

**Detected HID devices** (bottom section, Linux only)

- lists all HID devices currently connected to this machine with their `vendor:product`, name, handlers, and whether they are already trusted
- **Refresh Device List** — re-reads `/proc/bus/input/devices`
- **Add Selected Pair to Trusted** — adds the selected device's pair directly to the trusted list

#### Reports tab

Use this tab to review generated reports:

- browse recent `results/*_report.txt`
- filter by suspicious status and minimum score
- inspect full report content

## UI-first quick workflow

1. Build analyzer once (`analyzer/build/hid-analyzer`)
2. Launch UI: `python3 ui/desktop_app.py`
3. In **Trusted HID**, set allowlisted keyboard pairs and save
4. In **Run Capture**, start a capture, perform your scenario, then stop
5. In **Single Analysis**, analyze the captured trace directory
6. In **Reports**, review score, verdict, and reasons
7. Optionally run **Batch Evaluation** for dataset-level metrics

## Data and report outputs

Typical capture output files:

- `exec.jsonl`
- `fork.jsonl`
- `connect.jsonl`
- `hid.jsonl`

Typical report outputs:

- `results/<run>_report.txt`
- `results/summary.tsv` (batch flow)

## Optional CLI usage (without UI)

You can still run the analyzer directly:

```text
hid-analyzer <input.jsonl> [more.jsonl ...]
hid-analyzer --out <report.txt> <input.jsonl> [...]
```

Example:

```bash
./analyzer/build/hid-analyzer --out results/run_report.txt \
  data/trace_<timestamp>/exec.jsonl \
  data/trace_<timestamp>/fork.jsonl \
  data/trace_<timestamp>/connect.jsonl \
  data/trace_<timestamp>/hid.jsonl
```

## Limitations

- Runtime telemetry collection is Linux-focused (`bpftrace` + `udevadm`)
- Detector logic is heuristic scoring and may require threshold tuning
- HID provenance captures attach/remove metadata, not keystroke content

## Reference

- UI command contracts and design notes: `ui/DESKTOP_INTERFACE.md`

