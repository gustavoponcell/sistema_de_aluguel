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

    def upsert(
        self,
        rental_id: int,
        doc_type: DocumentType,
        file_path: str,
        generated_at: str,
        checksum: str,
    ) -> Document:
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO documents (
                    rental_id,
                    doc_type,
                    file_path,
                    generated_at,
                    checksum
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(rental_id, doc_type)
                DO UPDATE SET
                    file_path = excluded.file_path,
                    generated_at = excluded.generated_at,
                    checksum = excluded.checksum
                """,
                (
                    rental_id,
                    doc_type.value,
                    file_path,
                    generated_at,
                    checksum,
                ),
            )
        except Exception:
            self._logger.exception(
                "Failed to upsert document rental_id=%s doc_type=%s",
                rental_id,
                doc_type,
            )
            raise
        return Document(
            id=int(cursor.lastrowid) if cursor.lastrowid else None,
            rental_id=rental_id,
            doc_type=doc_type,
            file_path=file_path,
            generated_at=generated_at,
            checksum=checksum,
        )

    def get_latest(
        self,
        rental_id: int,
        doc_type: DocumentType,
    ) -> Optional[Document]:
        try:
            row = self._connection.execute(
                """
                SELECT *
                FROM documents
                WHERE rental_id = ?
                  AND doc_type = ?
                ORDER BY generated_at DESC, id DESC
                LIMIT 1
                """,
                (rental_id, doc_type.value),
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch latest document rental_id=%s doc_type=%s",
                rental_id,
                doc_type,
            )
            raise
        return document_from_row(row) if row else None
