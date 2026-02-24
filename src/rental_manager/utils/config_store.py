"""Shared JSON configuration storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config_data(config_path: Path) -> dict[str, Any]:
    """Load configuration JSON data from disk."""
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def save_config_data(config_path: Path, data: dict[str, Any]) -> None:
    """Persist configuration JSON data to disk."""
    config_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
