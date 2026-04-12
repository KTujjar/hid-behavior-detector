from __future__ import annotations

import os
import platform
import signal
from datetime import date, timedelta
from pathlib import Path
import re
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional

from config import load_config, save_config
from parsers import (
    ParsedReport,
    parse_evaluation_stdout,
    parse_report_file,
    parse_report_text,
    parse_summary_file,
)
from workflows import CommandSpec, WorkflowAdapter


_POSIX = platform.system().lower() != "windows"


class RunningProcess:
    def __init__(
        self,
        spec: CommandSpec,
        on_output: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        self.spec = spec
        self.on_output = on_output
        self.on_finish = on_finish
        self._proc: Optional[subprocess.Popen[str]] = None
        self._stop_requested = False
        self._send_newline_on_stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        popen_kwargs: dict = dict(
            cwd=str(self.spec.cwd),
            env=self.spec.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        # Put the child in its own process group so that killing the group
        # also terminates any background subprocesses it spawns (e.g. bpftrace
        # children). Without this, those children keep the stdout pipe open
        # after bash exits and on_finish is never reached.
        if _POSIX:
            popen_kwargs["start_new_session"] = True

        try:
            self._proc = subprocess.Popen(self.spec.argv, **popen_kwargs)
        except FileNotFoundError as exc:
            self.on_output(f"[error] missing command: {exc}\n")
            self.on_finish(127)
            return
        except Exception as exc:  # pragma: no cover
            self.on_output(f"[error] failed to start process: {exc}\n")
            self.on_finish(1)
            return

        # Handle stop() called before _proc was assigned.
        if self._stop_requested:
            self._terminate_proc(self._send_newline_on_stop)

        if self.spec.initial_input and self._proc.stdin:
            try:
                self._proc.stdin.write(self.spec.initial_input)
                self._proc.stdin.flush()
            except OSError:
                pass

        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self.on_output(line)
        # Only this thread calls wait() so on_finish is always triggered.
        exit_code = self._proc.wait()
        self.on_finish(exit_code)

    def _terminate_proc(self, send_newline: bool) -> None:
        """Signal the process to stop. Safe to call from any thread."""
        if self._proc is None or self._proc.poll() is not None:
            return
        if send_newline and self._proc.stdin:
            try:
                self._proc.stdin.write("\n")
                self._proc.stdin.flush()
            except OSError:
                pass
        if self._proc.poll() is not None:
            return
        if _POSIX:
            # Kill the entire process group so background bpftrace children
            # and the hid monitor all die and release the stdout pipe.
            try:
                pgid = os.getpgid(self._proc.pid)
                os.killpg(pgid, signal.SIGTERM)
            except OSError:
                self._proc.terminate()
        else:
            self._proc.terminate()

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self, send_newline: bool = False) -> None:
        """Request the process to stop. Safe to call from the UI thread."""
        self._stop_requested = True
        self._send_newline_on_stop = send_newline
        if self._proc is not None:
            self._terminate_proc(send_newline)


class DesktopApp:
    def __init__(self, root: tk.Tk, project_root: Path) -> None:
        self.root = root
        self.project_root = project_root
        cfg = load_config(project_root)
        self.adapter = WorkflowAdapter(project_root, cfg.get("trusted_hid_pairs", ""))
        self.config_state = cfg

        self.capture_proc: Optional[RunningProcess] = None
        self.combined_proc: Optional[RunningProcess] = None
        self.analysis_proc: Optional[RunningProcess] = None
        self.batch_proc: Optional[RunningProcess] = None
        self.batch_eval_output = ""

        self._build_ui()
        self._refresh_reports()
        self._check_platform_notice()

    def _check_platform_notice(self) -> None:
        if platform.system().lower() != "linux":
            self._set_status(
                "Note: collection scripts require Linux, sudo, bpftrace, and udevadm."
            )

    def _build_ui(self) -> None:
        self.root.title("HID Behavior Detector Desktop")
        self.root.geometry("1200x820")

        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(self.root, textvariable=self.status_var, anchor="w")
        status.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=4)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.capture_tab = ttk.Frame(notebook)
        self.analysis_tab = ttk.Frame(notebook)
        self.batch_tab = ttk.Frame(notebook)
        self.trusted_tab = ttk.Frame(notebook)
        self.reports_tab = ttk.Frame(notebook)

        notebook.add(self.capture_tab, text="Run Capture")
        notebook.add(self.analysis_tab, text="Single Analysis")
        notebook.add(self.batch_tab, text="Batch Evaluation")
        notebook.add(self.trusted_tab, text="Trusted HID")
        notebook.add(self.reports_tab, text="Reports")

        self._build_capture_tab()
        self._build_analysis_tab()
        self._build_batch_tab()
        self._build_trusted_tab()
        self._build_reports_tab()

    def _build_capture_tab(self) -> None:
        controls = ttk.Frame(self.capture_tab)
        controls.pack(fill=tk.X, padx=8, pady=8)

        self.capture_start_btn = ttk.Button(
            controls, text="Start Capture (collect_trace.sh)", command=self._start_capture
        )
        self.capture_start_btn.grid(row=0, column=0, padx=4, pady=4, sticky="w")

        self.capture_stop_btn = ttk.Button(
            controls, text="Stop Capture", command=self._stop_capture, state=tk.DISABLED
        )
        self.capture_stop_btn.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(controls, text="Combined run type:").grid(
            row=1, column=0, padx=4, pady=4, sticky="w"
        )
        self.combined_type = tk.StringVar(value="normal")
        ttk.Combobox(
            controls,
            textvariable=self.combined_type,
            values=["normal", "scripted"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, padx=4, pady=4, sticky="w")

        self.combined_start_btn = ttk.Button(
            controls, text="Start Combined Trace", command=self._start_combined_trace
        )
        self.combined_start_btn.grid(row=1, column=2, padx=4, pady=4, sticky="w")

        self.combined_stop_btn = ttk.Button(
            controls, text="Stop Combined Trace", command=self._stop_combined_trace, state=tk.DISABLED
        )
        self.combined_stop_btn.grid(row=1, column=3, padx=4, pady=4, sticky="w")

        ttk.Label(
            controls,
            text="Tip: trusted HID pairs from Trusted HID tab are injected via TRUSTED_HID_PAIRS.",
        ).grid(row=2, column=0, columnspan=4, padx=4, pady=4, sticky="w")

        self.capture_log = tk.Text(self.capture_tab, wrap="word", height=32)
        self.capture_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _build_analysis_tab(self) -> None:
        controls = ttk.Frame(self.analysis_tab)
        controls.pack(fill=tk.X, padx=8, pady=8)

        self.analysis_mode = tk.StringVar(value="trace_dir")
        ttk.Radiobutton(
            controls, text="Analyze trace directory", variable=self.analysis_mode, value="trace_dir"
        ).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Radiobutton(
            controls, text="Analyze JSONL files", variable=self.analysis_mode, value="files"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        self.trace_dir_var = tk.StringVar()
        ttk.Label(controls, text="Trace dir:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(controls, textvariable=self.trace_dir_var, width=70).grid(
            row=1, column=1, sticky="we", padx=4, pady=4
        )
        ttk.Button(controls, text="Browse", command=self._pick_trace_dir).grid(
            row=1, column=2, sticky="w", padx=4, pady=4
        )

        self.analysis_files: List[Path] = []
        self.files_var = tk.StringVar(value=[])
        ttk.Label(controls, text="JSONL files:").grid(row=2, column=0, sticky="nw", padx=4, pady=4)
        self.files_list = tk.Listbox(controls, listvariable=self.files_var, height=4, width=75)
        self.files_list.grid(row=2, column=1, sticky="we", padx=4, pady=4)
        file_buttons = ttk.Frame(controls)
        file_buttons.grid(row=2, column=2, sticky="n", padx=4, pady=4)
        ttk.Button(file_buttons, text="Add Files", command=self._add_analysis_files).pack(fill=tk.X)
        ttk.Button(file_buttons, text="Clear", command=self._clear_analysis_files).pack(fill=tk.X, pady=(6, 0))

        self.out_path_var = tk.StringVar(value=str(self.project_root / "results" / "manual_report.txt"))
        ttk.Label(controls, text="Output report path:").grid(
            row=3, column=0, sticky="w", padx=4, pady=4
        )
        ttk.Entry(controls, textvariable=self.out_path_var, width=70).grid(
            row=3, column=1, sticky="we", padx=4, pady=4
        )
        ttk.Button(controls, text="Browse", command=self._pick_out_file).grid(
            row=3, column=2, sticky="w", padx=4, pady=4
        )

        self.analysis_run_btn = ttk.Button(controls, text="Run Analysis", command=self._run_analysis)
        self.analysis_run_btn.grid(row=4, column=0, padx=4, pady=8, sticky="w")

        for col in (0, 1, 2):
            controls.grid_columnconfigure(col, weight=1 if col == 1 else 0)

        panes = ttk.Panedwindow(self.analysis_tab, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=1)

        ttk.Label(left, text="Process Output").pack(anchor="w")
        self.analysis_log = tk.Text(left, wrap="word", height=18)
        self.analysis_log.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="Parsed Report").pack(anchor="w")
        self.parsed_report_box = tk.Text(right, wrap="word", height=18)
        self.parsed_report_box.pack(fill=tk.BOTH, expand=True)

    def _build_batch_tab(self) -> None:
        controls = ttk.Frame(self.batch_tab)
        controls.pack(fill=tk.X, padx=8, pady=8)

        self.batch_run_btn = ttk.Button(
            controls, text="Run Batch + Evaluate", command=self._run_batch_and_evaluate
        )
        self.batch_run_btn.grid(row=0, column=0, padx=4, pady=4, sticky="w")

        self.batch_status_var = tk.StringVar(value="No batch run yet.")
        ttk.Label(controls, textvariable=self.batch_status_var).grid(
            row=0, column=1, columnspan=3, padx=4, pady=4, sticky="w"
        )

        ttk.Label(controls, text="Include runs since:").grid(
            row=1, column=0, padx=4, pady=4, sticky="w"
        )
        _SINCE_OPTIONS = ["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Custom date"]
        self.batch_since_choice = tk.StringVar(value="All time")
        since_combo = ttk.Combobox(
            controls,
            textvariable=self.batch_since_choice,
            values=_SINCE_OPTIONS,
            state="readonly",
            width=14,
        )
        since_combo.grid(row=1, column=1, padx=4, pady=4, sticky="w")
        since_combo.bind("<<ComboboxSelected>>", self._on_batch_since_changed)

        self.batch_since_date_var = tk.StringVar(value="")
        self.batch_since_entry = ttk.Entry(
            controls, textvariable=self.batch_since_date_var, width=12
        )
        self.batch_since_entry.grid(row=1, column=2, padx=4, pady=4, sticky="w")
        self.batch_since_entry.config(state=tk.DISABLED)

        ttk.Label(controls, text="(YYYY-MM-DD)").grid(
            row=1, column=3, padx=2, pady=4, sticky="w"
        )

        panes = ttk.Panedwindow(self.batch_tab, orient=tk.VERTICAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        upper = ttk.Frame(panes)
        lower = ttk.Frame(panes)
        panes.add(upper, weight=1)
        panes.add(lower, weight=1)

        cols = ("run", "type", "score", "flagged")
        self.summary_table = ttk.Treeview(upper, columns=cols, show="headings", height=8)
        for c in cols:
            self.summary_table.heading(c, text=c)
            self.summary_table.column(c, width=140 if c == "run" else 90, anchor="w")
        self.summary_table.pack(fill=tk.BOTH, expand=True)

        self.batch_metrics_var = tk.StringVar(value="TP: 0  TN: 0  FP: 0  FN: 0")
        ttk.Label(lower, textvariable=self.batch_metrics_var).pack(anchor="w", pady=(0, 4))
        self.batch_log = tk.Text(lower, wrap="word", height=14)
        self.batch_log.pack(fill=tk.BOTH, expand=True)

    def _build_trusted_tab(self) -> None:
        frame = ttk.Frame(self.trusted_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        ttk.Label(frame, text="Trusted HID Pairs").pack(anchor="w")

        list_row = ttk.Frame(frame)
        list_row.pack(fill=tk.X, pady=(4, 0))

        self.trusted_pairs_listbox = tk.Listbox(
            list_row, height=6, selectmode=tk.SINGLE, exportselection=False
        )
        self.trusted_pairs_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

        list_btns = ttk.Frame(list_row)
        list_btns.pack(side=tk.LEFT, padx=(8, 0), anchor="n")
        ttk.Button(list_btns, text="Add Pair", command=self._add_trusted_pair_dialog).pack(
            fill=tk.X, pady=(0, 4)
        )
        ttk.Button(list_btns, text="Remove Selected", command=self._remove_selected_trusted_pair).pack(
            fill=tk.X
        )

        self._refresh_trusted_pairs_listbox()

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Save + Apply", command=self._save_trusted_pairs).pack(
            side=tk.LEFT, padx=(0, 4)
        )

        self.trusted_status_var = tk.StringVar(value="Current session value loaded from config.")
        ttk.Label(frame, textvariable=self.trusted_status_var).pack(anchor="w", pady=(8, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))
        ttk.Label(frame, text="Detected HID devices on this computer").pack(anchor="w")

        hid_controls = ttk.Frame(frame)
        hid_controls.pack(fill=tk.X, pady=(4, 6))
        ttk.Button(hid_controls, text="Refresh Device List", command=self._refresh_local_hid_devices).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(
            hid_controls,
            text="Add Selected Pair to Trusted",
            command=self._add_selected_hid_pair_to_trusted,
        ).pack(side=tk.LEFT, padx=4)

        hid_cols = ("pair", "name", "handlers", "trusted")
        self.local_hid_table = ttk.Treeview(frame, columns=hid_cols, show="headings", height=10)
        self.local_hid_table.heading("pair", text="vendor:product")
        self.local_hid_table.heading("name", text="Device Name")
        self.local_hid_table.heading("handlers", text="Handlers")
        self.local_hid_table.heading("trusted", text="Trusted")
        self.local_hid_table.column("pair", width=140, anchor="w")
        self.local_hid_table.column("name", width=380, anchor="w")
        self.local_hid_table.column("handlers", width=280, anchor="w")
        self.local_hid_table.column("trusted", width=90, anchor="center")
        self.local_hid_table.pack(fill=tk.BOTH, expand=True)
        self._refresh_local_hid_devices()

    def _build_reports_tab(self) -> None:
        controls = ttk.Frame(self.reports_tab)
        controls.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(controls, text="Suspicious filter:").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.report_filter = tk.StringVar(value="all")
        ttk.Combobox(
            controls, textvariable=self.report_filter, values=["all", "yes", "no"], state="readonly", width=8
        ).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(controls, text="Min score:").grid(row=0, column=2, padx=4, pady=4, sticky="w")
        self.min_score_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.min_score_var, width=10).grid(
            row=0, column=3, padx=4, pady=4, sticky="w"
        )

        ttk.Button(controls, text="Refresh", command=self._refresh_reports).grid(
            row=0, column=4, padx=4, pady=4, sticky="w"
        )

        body = ttk.Panedwindow(self.reports_tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)

        self.report_paths: List[Path] = []
        self.report_list_var = tk.StringVar(value=[])
        self.report_list = tk.Listbox(left, listvariable=self.report_list_var)
        self.report_list.pack(fill=tk.BOTH, expand=True)
        self.report_list.bind("<<ListboxSelect>>", self._on_report_select)

        self.report_text = tk.Text(right, wrap="word")
        self.report_text.pack(fill=tk.BOTH, expand=True)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _append_text(self, widget: tk.Text, text: str) -> None:
        widget.insert(tk.END, text)
        widget.see(tk.END)

    def _ui_output(self, widget: tk.Text, line: str) -> None:
        self.root.after(0, lambda: self._append_text(widget, line))

    def _start_capture(self) -> None:
        if self.capture_proc and self.capture_proc.is_running():
            return
        spec = self.adapter.collect_trace()
        self.capture_log.delete("1.0", tk.END)
        self.capture_start_btn.config(state=tk.DISABLED)
        self.capture_stop_btn.config(state=tk.NORMAL)
        self._set_status("Collect trace running...")
        self.capture_proc = RunningProcess(
            spec,
            on_output=lambda line: self._ui_output(self.capture_log, line),
            on_finish=lambda code: self.root.after(0, lambda: self._on_capture_finished(code)),
        )
        self.capture_proc.start()

    def _stop_capture(self) -> None:
        if self.capture_proc:
            self.capture_proc.stop(send_newline=True)

    def _on_capture_finished(self, code: int) -> None:
        self.capture_start_btn.config(state=tk.NORMAL)
        self.capture_stop_btn.config(state=tk.DISABLED)
        self._append_text(self.capture_log, f"\n[exit] collect_trace finished with code {code}\n")
        self._set_status("Collect trace stopped.")
        self._refresh_reports()

    def _start_combined_trace(self) -> None:
        if self.combined_proc and self.combined_proc.is_running():
            return
        run_type = self.combined_type.get().strip().lower()
        spec = self.adapter.combined_trace(run_type)
        self.combined_start_btn.config(state=tk.DISABLED)
        self.combined_stop_btn.config(state=tk.NORMAL)
        self._set_status(f"Combined trace ({run_type}) running...")
        self.combined_proc = RunningProcess(
            spec,
            on_output=lambda line: self._ui_output(self.capture_log, line),
            on_finish=lambda code: self.root.after(0, lambda: self._on_combined_finished(code)),
        )
        self.combined_proc.start()

    def _stop_combined_trace(self) -> None:
        if self.combined_proc:
            self.combined_proc.stop(send_newline=False)

    def _on_combined_finished(self, code: int) -> None:
        self.combined_start_btn.config(state=tk.NORMAL)
        self.combined_stop_btn.config(state=tk.DISABLED)
        self._append_text(self.capture_log, f"\n[exit] combined trace finished with code {code}\n")
        self._set_status("Combined trace stopped.")
        self._refresh_reports()

    def _pick_trace_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.project_root / "data"))
        if selected:
            self.trace_dir_var.set(selected)

    def _add_analysis_files(self) -> None:
        files = filedialog.askopenfilenames(
            initialdir=str(self.project_root / "data"),
            filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")],
        )
        for f in files:
            p = Path(f)
            if p not in self.analysis_files:
                self.analysis_files.append(p)
        self.files_var.set([str(p) for p in self.analysis_files])

    def _clear_analysis_files(self) -> None:
        self.analysis_files.clear()
        self.files_var.set([])

    def _pick_out_file(self) -> None:
        selected = filedialog.asksaveasfilename(
            initialdir=str(self.project_root / "results"),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if selected:
            self.out_path_var.set(selected)

    def _run_analysis(self) -> None:
        if self.analysis_proc and self.analysis_proc.is_running():
            messagebox.showinfo("Analysis", "Analysis is already running.")
            return

        out_path_text = self.out_path_var.get().strip()
        out_path = Path(out_path_text) if out_path_text else None
        mode = self.analysis_mode.get()
        try:
            if mode == "trace_dir":
                trace_dir = Path(self.trace_dir_var.get().strip())
                if not trace_dir.exists():
                    raise ValueError("Select a valid trace directory.")
                spec = self.adapter.analyze_trace_dir(trace_dir)
            else:
                spec = self.adapter.analyze_files(self.analysis_files, out_path)
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.analysis_log.delete("1.0", tk.END)
        self.parsed_report_box.delete("1.0", tk.END)
        self.analysis_run_btn.config(state=tk.DISABLED)
        self._set_status("Running analysis...")

        self.analysis_proc = RunningProcess(
            spec,
            on_output=lambda line: self._ui_output(self.analysis_log, line),
            on_finish=lambda code: self.root.after(
                0, lambda: self._on_analysis_finished(code, mode, out_path)
            ),
        )
        self.analysis_proc.start()

    def _on_analysis_finished(self, code: int, mode: str, out_path: Optional[Path]) -> None:
        self.analysis_run_btn.config(state=tk.NORMAL)
        self._append_text(self.analysis_log, f"\n[exit] analysis finished with code {code}\n")
        self._set_status("Analysis complete.")
        if code != 0:
            return

        report_path: Optional[Path] = None
        if mode == "trace_dir":
            trace_dir = Path(self.trace_dir_var.get().strip())
            report_path = self.project_root / "results" / f"{trace_dir.name}_merged_report.txt"
        elif out_path:
            report_path = out_path

        parsed: Optional[ParsedReport] = None
        if report_path and report_path.exists():
            parsed = parse_report_file(report_path)
        else:
            parsed = parse_report_text(self.analysis_log.get("1.0", tk.END))

        self._render_parsed_report(parsed)
        self._refresh_reports()

    def _render_parsed_report(self, parsed: ParsedReport) -> None:
        self.parsed_report_box.delete("1.0", tk.END)
        for key, value in parsed.fields.items():
            self._append_text(self.parsed_report_box, f"{key}: {value}\n")
        if parsed.reasons:
            self._append_text(self.parsed_report_box, "\nReasons:\n")
            for reason in parsed.reasons:
                self._append_text(self.parsed_report_box, f"- {reason}\n")

    def _on_batch_since_changed(self, _event: object = None) -> None:
        choice = self.batch_since_choice.get()
        days_map = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
        if choice in days_map:
            since = date.today() - timedelta(days=days_map[choice])
            self.batch_since_date_var.set(since.isoformat())
            self.batch_since_entry.config(state=tk.DISABLED)
        elif choice == "Custom date":
            self.batch_since_entry.config(state=tk.NORMAL)
            self.batch_since_entry.focus_set()
        else:
            self.batch_since_date_var.set("")
            self.batch_since_entry.config(state=tk.DISABLED)

    def _get_batch_since_date(self) -> Optional[str]:
        choice = self.batch_since_choice.get()
        if choice == "All time":
            return None
        raw = self.batch_since_date_var.get().strip()
        if not raw:
            return None
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            messagebox.showerror("Invalid date", f"Expected YYYY-MM-DD, got: {raw!r}")
            return None
        return raw

    def _run_batch_and_evaluate(self) -> None:
        if self.batch_proc and self.batch_proc.is_running():
            messagebox.showinfo("Batch", "Batch workflow is already running.")
            return

        since_date = self._get_batch_since_date()
        if since_date is None and self.batch_since_choice.get() != "All time":
            return  # validation failed inside _get_batch_since_date

        self.batch_log.delete("1.0", tk.END)
        self.batch_eval_output = ""
        self.batch_run_btn.config(state=tk.DISABLED)
        label = f"since {since_date}" if since_date else "all time"
        self.batch_status_var.set(f"Running batch_analyze.sh ({label}) ...")
        self._set_status("Batch workflow running...")

        spec = self.adapter.batch_analyze(since_date=since_date)
        self.batch_proc = RunningProcess(
            spec,
            on_output=lambda line: self._ui_output(self.batch_log, line),
            on_finish=lambda code: self.root.after(0, lambda: self._on_batch_finished(code)),
        )
        self.batch_proc.start()

    def _on_batch_finished(self, code: int) -> None:
        self._append_text(self.batch_log, f"\n[exit] batch_analyze finished with code {code}\n")
        if code != 0:
            self.batch_run_btn.config(state=tk.NORMAL)
            self.batch_status_var.set("Batch failed.")
            return

        self.batch_status_var.set("Running evaluate_summary.sh ...")
        eval_spec = self.adapter.evaluate_summary()
        self.batch_proc = RunningProcess(
            eval_spec,
            on_output=lambda line: self._on_eval_output(line),
            on_finish=lambda eval_code: self.root.after(0, lambda: self._on_eval_finished(eval_code)),
        )
        self.batch_proc.start()

    def _on_eval_output(self, line: str) -> None:
        self.batch_eval_output += line
        self._ui_output(self.batch_log, line)

    def _on_eval_finished(self, code: int) -> None:
        self._append_text(self.batch_log, f"\n[exit] evaluate_summary finished with code {code}\n")
        self.batch_run_btn.config(state=tk.NORMAL)
        self.batch_status_var.set("Batch workflow complete." if code == 0 else "Evaluation failed.")
        metrics = parse_evaluation_stdout(self.batch_eval_output)
        self.batch_metrics_var.set(
            f"TP: {metrics['tp']}  TN: {metrics['tn']}  FP: {metrics['fp']}  FN: {metrics['fn']}"
        )
        self._load_summary_table()
        self._refresh_reports()
        self._set_status("Batch workflow complete.")

    def _normalize_pairs(self, text: str) -> str:
        text = text.replace("\n", ",")
        raw_tokens = [t.strip() for t in text.split(",") if t.strip()]
        return ",".join(raw_tokens)

    def _save_trusted_pairs(self) -> None:
        pairs = list(self.trusted_pairs_listbox.get(0, tk.END))
        normalized = ",".join(pairs)
        self.config_state["trusted_hid_pairs"] = normalized
        save_config(self.project_root, self.config_state)
        self.adapter.set_trusted_pairs(normalized)
        self.trusted_status_var.set("Saved and applied to new runs.")
        self._set_status("Trusted HID pairs saved.")
        if hasattr(self, "local_hid_table"):
            self._refresh_local_hid_devices()

    def _refresh_trusted_pairs_listbox(self) -> None:
        if not hasattr(self, "trusted_pairs_listbox"):
            return
        self.trusted_pairs_listbox.delete(0, tk.END)
        normalized = self._normalize_pairs(self.config_state.get("trusted_hid_pairs", ""))
        for pair in normalized.split(","):
            if pair.strip():
                self.trusted_pairs_listbox.insert(tk.END, pair.strip())

    def _add_trusted_pair_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Trusted Pair")
        dialog.resizable(False, False)
        dialog.grab_set()

        ttk.Label(dialog, text="Enter vendor:product (e.g. 046d:c31c):").pack(padx=16, pady=(14, 4))
        entry_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=entry_var, width=20)
        entry.pack(padx=16, pady=(0, 10))
        entry.focus_set()

        status_var = tk.StringVar()
        ttk.Label(dialog, textvariable=status_var, foreground="red").pack(padx=16)

        def _confirm() -> None:
            pair = entry_var.get().strip().lower()
            if not re.match(r"^[a-f0-9]{4}:[a-f0-9]{4}$", pair):
                status_var.set("Invalid format. Use hex vendor:product e.g. 046d:c31c")
                return
            existing = list(self.trusted_pairs_listbox.get(0, tk.END))
            if pair in existing:
                status_var.set(f"{pair} is already in the list.")
                return
            self.trusted_pairs_listbox.insert(tk.END, pair)
            self.trusted_status_var.set(f"Added {pair}. Click Save + Apply to persist.")
            if hasattr(self, "local_hid_table"):
                self._refresh_local_hid_devices()
            dialog.destroy()

        btn_row = ttk.Frame(dialog)
        btn_row.pack(pady=(6, 14))
        ttk.Button(btn_row, text="Add", command=_confirm).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=6)
        dialog.bind("<Return>", lambda _e: _confirm())
        dialog.bind("<Escape>", lambda _e: dialog.destroy())

    def _remove_selected_trusted_pair(self) -> None:
        if not self.trusted_pairs_listbox.curselection():
            messagebox.showinfo("Trusted HID", "Select a pair from the list first.")
            return
        idx = self.trusted_pairs_listbox.curselection()[0]
        pair = self.trusted_pairs_listbox.get(idx)
        self.trusted_pairs_listbox.delete(idx)
        self.trusted_status_var.set(f"Removed {pair}. Click Save + Apply to persist.")
        if hasattr(self, "local_hid_table"):
            self._refresh_local_hid_devices()

    def _current_trusted_pair_set(self) -> set[str]:
        return {p.lower() for p in self.trusted_pairs_listbox.get(0, tk.END)}

    def _discover_local_hid_devices(self) -> List[Dict[str, str]]:
        if platform.system().lower() != "linux":
            return []
        devices_path = Path("/proc/bus/input/devices")
        if not devices_path.exists():
            return []

        try:
            text = devices_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        discovered: List[Dict[str, str]] = []
        seen = set()
        blocks = [b for b in text.split("\n\n") if b.strip()]
        for block in blocks:
            info_line = ""
            name = ""
            handlers = ""
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("I:"):
                    info_line = line
                elif line.startswith("N:"):
                    m_name = re.search(r'Name="(.*)"', line)
                    if m_name:
                        name = m_name.group(1).strip()
                elif line.startswith("H:"):
                    m_handlers = re.search(r"Handlers=(.*)", line)
                    if m_handlers:
                        handlers = m_handlers.group(1).strip()

            match = re.search(r"Vendor=([0-9A-Fa-f]{4})\s+Product=([0-9A-Fa-f]{4})", info_line)
            if not match:
                continue

            handlers_lower = handlers.lower()
            # Keep only user-facing HID classes that are relevant for trust controls.
            if not any(key in handlers_lower for key in ("kbd", "mouse", "js", "event")):
                continue

            pair = f"{match.group(1).lower()}:{match.group(2).lower()}"
            unique_key = (pair, name, handlers)
            if unique_key in seen:
                continue
            seen.add(unique_key)
            discovered.append({"pair": pair, "name": name, "handlers": handlers})

        discovered.sort(key=lambda d: (d["pair"], d["name"]))
        return discovered

    def _refresh_local_hid_devices(self) -> None:
        for item in self.local_hid_table.get_children():
            self.local_hid_table.delete(item)

        if platform.system().lower() != "linux":
            self.trusted_status_var.set("Device detection list is available on Linux hosts.")
            return

        devices = self._discover_local_hid_devices()
        trusted_pairs = self._current_trusted_pair_set()
        for d in devices:
            is_trusted = "yes" if d["pair"] in trusted_pairs else "no"
            self.local_hid_table.insert(
                "",
                tk.END,
                values=(d["pair"], d["name"] or "(unknown)", d["handlers"] or "-", is_trusted),
            )

        if devices:
            self.trusted_status_var.set(f"Loaded {len(devices)} local HID device(s).")
        else:
            self.trusted_status_var.set("No HID devices discovered from /proc/bus/input/devices.")

    def _add_selected_hid_pair_to_trusted(self) -> None:
        if not self.local_hid_table.selection():
            messagebox.showinfo("Trusted HID", "Select a device row first.")
            return

        selected = self.local_hid_table.item(self.local_hid_table.selection()[0]).get("values", [])
        if not selected:
            return
        pair = str(selected[0]).strip().lower()
        if not re.match(r"^[a-f0-9]{4}:[a-f0-9]{4}$", pair):
            messagebox.showerror("Trusted HID", f"Invalid selected pair: {pair}")
            return

        pairs = self._current_trusted_pair_set()
        if pair in pairs:
            self.trusted_status_var.set(f"{pair} already in trusted list.")
            return

        self.trusted_pairs_listbox.insert(tk.END, pair)
        self.trusted_status_var.set(f"Added {pair} to trusted list. Click Save + Apply to persist.")
        self._refresh_local_hid_devices()

    def _load_summary_table(self) -> None:
        for item in self.summary_table.get_children():
            self.summary_table.delete(item)
        summary_path = self.project_root / "results" / "summary.tsv"
        if not summary_path.exists():
            return
        rows = parse_summary_file(summary_path)
        for row in rows:
            self.summary_table.insert(
                "", tk.END, values=(row.get("run", ""), row.get("type", ""), row.get("score", ""), row.get("flagged", ""))
            )

    def _refresh_reports(self) -> None:
        results_dir = self.project_root / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(results_dir.glob("*_report.txt"), key=lambda p: p.stat().st_mtime, reverse=True)

        wanted = self.report_filter.get() if hasattr(self, "report_filter") else "all"
        min_score_text = self.min_score_var.get().strip() if hasattr(self, "min_score_var") else ""
        min_score = int(min_score_text) if min_score_text.isdigit() else None

        filtered: List[Path] = []
        for path in files:
            try:
                parsed = parse_report_file(path)
            except OSError:
                continue
            suspicious = parsed.fields.get("Suspicious", "").lower()
            score_text = parsed.fields.get("Suspicion score", "0")
            try:
                score = int(score_text)
            except ValueError:
                score = 0
            if wanted != "all" and suspicious != wanted:
                continue
            if min_score is not None and score < min_score:
                continue
            filtered.append(path)

        self.report_paths = filtered
        names = [p.name for p in filtered]
        self.report_list_var.set(names)
        self._load_summary_table()

    def _on_report_select(self, _event: object) -> None:
        if not self.report_list.curselection():
            return
        idx = self.report_list.curselection()[0]
        if idx >= len(self.report_paths):
            return
        path = self.report_paths[idx]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Read error", str(exc))
            return
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", text)


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    root = tk.Tk()
    DesktopApp(root, project_root)
    root.mainloop()


if __name__ == "__main__":
    main()
