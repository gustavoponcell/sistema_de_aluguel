"""Local audit logging for assistant usage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rental_manager.logging_config import get_logger
from rental_manager.paths import get_logs_dir

_LOGGER = get_logger(__name__)
_AUDIT_FILENAME = "assistant_audit.log"


def _get_audit_path() -> Path:
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / _AUDIT_FILENAME


def log_assistant_event(action: str) -> None:
    """Append a sanitized audit entry."""
    if not action:
        return
    entry = f"{datetime.now().isoformat(timespec='seconds')} | {action}\n"
    try:
        path = _get_audit_path()
        with path.open("a", encoding="utf-8") as stream:
            stream.write(entry)
    except OSError:
        _LOGGER.warning("Falha ao registrar auditoria do assistente.")
