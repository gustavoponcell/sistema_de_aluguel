"""Document service exposing repo access to the UI."""

from __future__ import annotations

import sqlite3
from typing import Optional

from rental_manager.domain.models import Document, DocumentType
from rental_manager.repositories.document_repo import DocumentRepository


class DocumentService:
    """Thin service wrapper that enforces UI -> service -> repo."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        repo: DocumentRepository | None = None,
    ) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._repo = repo or DocumentRepository(connection)

    def list_documents(
        self,
        *,
        doc_type: Optional[DocumentType] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        customer_search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Document]:
        return self._repo.list_documents(
            doc_type=doc_type,
            start_date=start_date,
            end_date=end_date,
            customer_search=customer_search,
            limit=limit,
            offset=offset,
        )

    def add_document(self, document: Document) -> Document:
        """Persist a generated document entry."""
        return self._repo.add(document)

    def get_latest_document(
        self,
        order_id: int,
        doc_type: DocumentType,
    ) -> Optional[Document]:
        """Return the latest generated document for a rental."""
        return self._repo.get_latest(order_id, doc_type)
