"""Repository for generated documents persistence."""

from __future__ import annotations

import sqlite3
from typing import Optional

from rental_manager.domain.models import Document, DocumentType
from rental_manager.logging_config import get_logger
from rental_manager.repositories.mappers import document_from_row


class DocumentRepository:
    """Data access for generated rental documents."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._logger = get_logger(self.__class__.__name__)

    def add(self, document: Document) -> Document:
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO documents (
                    created_at,
                    type,
                    customer_name,
                    reference_date,
                    file_name,
                    file_path,
                    order_id,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.created_at,
                    document.doc_type.value,
                    document.customer_name,
                    document.reference_date,
                    document.file_name,
                    document.file_path,
                    document.order_id,
                    document.notes,
                ),
            )
        except Exception:
            self._logger.exception(
                "Failed to insert document order_id=%s type=%s",
                document.order_id,
                document.doc_type,
            )
            raise
        return Document(
            id=int(cursor.lastrowid) if cursor.lastrowid else None,
            created_at=document.created_at,
            doc_type=document.doc_type,
            customer_name=document.customer_name,
            reference_date=document.reference_date,
            file_name=document.file_name,
            file_path=document.file_path,
            order_id=document.order_id,
            notes=document.notes,
        )

    def get_latest(
        self,
        order_id: int,
        doc_type: DocumentType,
    ) -> Optional[Document]:
        try:
            row = self._connection.execute(
                """
                SELECT *
                FROM documents
                WHERE order_id = ?
                  AND type = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (order_id, doc_type.value),
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch latest document order_id=%s doc_type=%s",
                order_id,
                doc_type,
            )
            raise
        return document_from_row(row) if row else None

    def list_documents(
        self,
        *,
        doc_type: Optional[DocumentType] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        customer_search: Optional[str] = None,
    ) -> list[Document]:
        filters = []
        params: list[object] = []

        if doc_type is not None:
            filters.append("type = ?")
            params.append(doc_type.value)

        if start_date:
            filters.append("reference_date >= ?")
            params.append(start_date)

        if end_date:
            filters.append("reference_date <= ?")
            params.append(end_date)

        if customer_search:
            filters.append("LOWER(customer_name) LIKE ?")
            params.append(f"%{customer_search.lower()}%")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"""
            SELECT *
            FROM documents
            {where_clause}
            ORDER BY reference_date DESC, created_at DESC, id DESC
        """
        try:
            rows = self._connection.execute(query, params).fetchall()
        except Exception:
            self._logger.exception("Failed to list documents")
            raise
        return [document_from_row(row) for row in rows]
