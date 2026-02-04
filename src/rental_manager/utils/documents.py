"""Document settings storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import re

from rental_manager.domain.models import DocumentType
from rental_manager.utils.config_store import load_config_data, save_config_data


@dataclass(frozen=True)
class DocumentsSettings:
    """Configuration for document storage paths."""

    documents_dir: str | None = None


def sanitize_filename(value: str) -> str:
    """Normalize text to be safe for filenames."""
    cleaned = " ".join(value.strip().split())
    cleaned = cleaned.replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)
    return cleaned or "Cliente"


def build_document_filename(
    customer_name: str,
    reference_date: str | None,
    doc_type: DocumentType,
) -> str:
    """Build default filename for a document."""
    base_name = sanitize_filename(customer_name)
    date_part = reference_date or ""
    label_map = {
        DocumentType.CONTRACT: "Contrato",
        DocumentType.RECEIPT: "Recibo",
        DocumentType.INVOICE: "Nota_Fiscal",
    }
    label = label_map.get(doc_type, doc_type.value)
    if date_part:
        return f"{base_name}_{date_part}_{label}.pdf"
    return f"{base_name}_{label}.pdf"


def load_documents_settings(config_path: Path) -> DocumentsSettings:
    """Load document settings from config JSON."""
    data = load_config_data(config_path)
    value = data.get("documents_dir")
    if isinstance(value, str) and value.strip():
        return DocumentsSettings(documents_dir=value)
    return DocumentsSettings()


def save_documents_settings(config_path: Path, settings: DocumentsSettings) -> None:
    """Persist document settings to config JSON."""
    payload = load_config_data(config_path)
    payload["documents_dir"] = settings.documents_dir
    save_config_data(config_path, payload)
