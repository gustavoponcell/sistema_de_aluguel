"""Storage for assistant-provided document drafts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from rental_manager.domain.models import DocumentType
from rental_manager.logging_config import get_logger
from rental_manager.paths import get_app_data_dir

_LOGGER = get_logger(__name__)
_FILENAME = "assistant_drafts.json"


@dataclass(slots=True)
class DocumentDraft:
    doc_type: DocumentType
    text: str
    updated_at: str


def _get_file() -> Path:
    return get_app_data_dir() / _FILENAME


def _load_all() -> dict[str, dict[str, str]]:
    path = _get_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _save_all(data: dict[str, dict[str, str]]) -> None:
    path = _get_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_draft(doc_type: DocumentType) -> Optional[DocumentDraft]:
    """Return the latest draft for the given document type."""
    data = _load_all().get(doc_type.value)
    if not isinstance(data, dict):
        return None
    text = data.get("text")
    updated_at = data.get("updated_at")
    if not isinstance(text, str) or not text.strip():
        return None
    if not isinstance(updated_at, str):
        updated_at = ""
    return DocumentDraft(doc_type=doc_type, text=text, updated_at=updated_at)


def save_draft(doc_type: DocumentType, text: str) -> None:
    """Persist a sanitized draft for future use."""
    text = text.strip()
    if not text:
        return
    payload = _load_all()
    payload[doc_type.value] = {
        "text": text,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        _save_all(payload)
    except OSError:
        _LOGGER.warning("Falha ao salvar rascunho do documento assistido.")


def clear_draft(doc_type: DocumentType) -> None:
    """Remove a stored draft."""
    payload = _load_all()
    if doc_type.value in payload:
        payload.pop(doc_type.value, None)
        try:
            _save_all(payload)
        except OSError:
            _LOGGER.warning("Falha ao limpar rascunho do documento assistido.")
