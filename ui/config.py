from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


CONFIG_FILENAME = ".hid_desktop_ui.json"


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_FILENAME


def load_config(project_root: Path) -> Dict[str, str]:
    path = config_path(project_root)
    if not path.exists():
        return {"trusted_hid_pairs": ""}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"trusted_hid_pairs": ""}
    trusted = data.get("trusted_hid_pairs", "")
    return {"trusted_hid_pairs": trusted if isinstance(trusted, str) else ""}


def save_config(project_root: Path, cfg: Dict[str, str]) -> None:
    path = config_path(project_root)
    payload = {"trusted_hid_pairs": cfg.get("trusted_hid_pairs", "")}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
