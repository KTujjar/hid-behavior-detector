from __future__ import annotations

from dataclasses import dataclass, field
import csv
from io import StringIO
from pathlib import Path
import re
from typing import Dict, List


@dataclass
class ParsedReport:
    fields: Dict[str, str] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


def parse_report_text(text: str) -> ParsedReport:
    fields: Dict[str, str] = {}
    reasons: List[str] = []
    in_reasons = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "Reasons:":
            in_reasons = True
            continue
        if in_reasons:
            if line.startswith("- "):
                reasons.append(line[2:].strip())
                continue
            if line.startswith("---"):
                continue
            # Keep parser resilient when report format changes.
            reasons.append(line)
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

    return ParsedReport(fields=fields, reasons=reasons)


def parse_report_file(path: Path) -> ParsedReport:
    return parse_report_text(path.read_text(encoding="utf-8", errors="replace"))


def parse_summary_tsv(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    reader = csv.DictReader(StringIO(text), delimiter="\t")
    for row in reader:
        if not row:
            continue
        rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def parse_summary_file(path: Path) -> List[Dict[str, str]]:
    return parse_summary_tsv(path.read_text(encoding="utf-8", errors="replace"))


_EVAL_PATTERNS = {
    "tp": re.compile(r"True positives.*?:\s*(\d+)", re.IGNORECASE),
    "tn": re.compile(r"True negatives.*?:\s*(\d+)", re.IGNORECASE),
    "fp": re.compile(r"False positives.*?:\s*(\d+)", re.IGNORECASE),
    "fn": re.compile(r"False negatives.*?:\s*(\d+)", re.IGNORECASE),
}


def parse_evaluation_stdout(text: str) -> Dict[str, int]:
    metrics = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for key, pattern in _EVAL_PATTERNS.items():
        match = pattern.search(text)
        if match:
            metrics[key] = int(match.group(1))
    return metrics
