from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Dict, List, Optional


@dataclass
class CommandSpec:
    name: str
    argv: List[str]
    cwd: Path
    env: Dict[str, str]
    initial_input: Optional[str] = None


class WorkflowAdapter:
    """Builds subprocess specs for all supported workflows."""

    def __init__(self, project_root: Path, trusted_pairs: str = "") -> None:
        self.project_root = project_root
        self.trusted_pairs = trusted_pairs.strip()

    def set_trusted_pairs(self, trusted_pairs: str) -> None:
        self.trusted_pairs = trusted_pairs.strip()

    def _base_env(self) -> Dict[str, str]:
        env = dict(os.environ)
        if self.trusted_pairs:
            env["TRUSTED_HID_PAIRS"] = self.trusted_pairs
        return env

    def _script_path(self, rel_path: str) -> str:
        return str(self.project_root / rel_path)

    def collect_trace(self) -> CommandSpec:
        return CommandSpec(
            name="collect_trace",
            argv=["bash", self._script_path("scripts/collect_trace.sh")],
            cwd=self.project_root,
            env=self._base_env(),
        )

    def combined_trace(self, run_type: str) -> CommandSpec:
        run_type = run_type.strip().lower()
        if run_type not in {"normal", "scripted"}:
            raise ValueError("run_type must be 'normal' or 'scripted'")
        return CommandSpec(
            name="combined_trace",
            argv=["bash", self._script_path("scripts/combined_trace_script.sh")],
            cwd=self.project_root,
            env=self._base_env(),
            initial_input=f"{run_type}\n",
        )

    def analyze_trace_dir(self, trace_dir: Path) -> CommandSpec:
        return CommandSpec(
            name="analyze_trace_dir",
            argv=["bash", self._script_path("scripts/analyze_trace_dir.sh"), str(trace_dir)],
            cwd=self.project_root,
            env=self._base_env(),
        )

    def analyze_files(self, files: List[Path], out_path: Optional[Path]) -> CommandSpec:
        if not files:
            raise ValueError("At least one input file is required")
        analyzer_bin = self.project_root / "analyzer" / "build" / "hid-analyzer"
        argv = [str(analyzer_bin)]
        if out_path:
            argv.extend(["--out", str(out_path)])
        argv.extend(str(p) for p in files)
        return CommandSpec(
            name="analyze_files",
            argv=argv,
            cwd=self.project_root,
            env=self._base_env(),
        )

    def batch_analyze(self, since_date: Optional[str] = None) -> CommandSpec:
        argv = ["bash", self._script_path("scripts/batch_analyze.sh")]
        if since_date:
            argv.extend(["--since", since_date])
        return CommandSpec(
            name="batch_analyze",
            argv=argv,
            cwd=self.project_root,
            env=self._base_env(),
        )

    def evaluate_summary(self, summary_path: Optional[Path] = None) -> CommandSpec:
        argv = ["bash", self._script_path("scripts/evaluate_summary.sh")]
        if summary_path:
            argv.append(str(summary_path))
        return CommandSpec(
            name="evaluate_summary",
            argv=argv,
            cwd=self.project_root,
            env=self._base_env(),
        )
