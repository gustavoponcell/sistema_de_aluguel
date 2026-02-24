"""Repository for payments persistence."""

from __future__ import annotations

import sqlite3
from typing import Optional

from rental_manager.domain.models import Payment
from rental_manager.logging_config import get_logger
from rental_manager.repositories.mappers import payment_from_row


class PaymentRepository:
    """Data access for payments."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._logger = get_logger(self.__class__.__name__)

    def list_by_rental(self, rental_id: int) -> list[Payment]:
        try:
            rows = self._connection.execute(
                """
                SELECT *
                FROM payments
                WHERE rental_id = ?
                ORDER BY paid_at IS NULL, paid_at, id
                """,
                (rental_id,),
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to list payments rental_id=%s", rental_id)
            raise
        return [payment_from_row(row) for row in rows]

    def get_by_id(self, payment_id: int) -> Optional[Payment]:
        try:
            row = self._connection.execute(
                "SELECT * FROM payments WHERE id = ?",
                (payment_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch payment id=%s", payment_id)
            raise
        return payment_from_row(row) if row else None

    def create(
        self,
        rental_id: int,
        amount: float,
        method: Optional[str],
        paid_at: Optional[str],
        note: Optional[str],
    ) -> Payment:
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO payments (rental_id, amount, method, paid_at, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (rental_id, amount, method, paid_at, note),
            )
        except Exception:
            self._logger.exception("Failed to create payment rental_id=%s", rental_id)
            raise
        return Payment(
            id=int(cursor.lastrowid),
            rental_id=rental_id,
            amount=amount,
            method=method,
            paid_at=paid_at,
            note=note,
        )

    def update(
        self,
        payment_id: int,
        amount: float,
        method: Optional[str],
        paid_at: Optional[str],
        note: Optional[str],
    ) -> bool:
        try:
            cursor = self._connection.execute(
                """
                UPDATE payments
                SET amount = ?,
                    method = ?,
                    paid_at = ?,
                    note = ?
                WHERE id = ?
                """,
                (amount, method, paid_at, note, payment_id),
            )
        except Exception:
            self._logger.exception("Failed to update payment id=%s", payment_id)
            raise
        return cursor.rowcount > 0

    def delete(self, payment_id: int) -> bool:
        try:
            cursor = self._connection.execute(
                "DELETE FROM payments WHERE id = ?",
                (payment_id,),
            )
        except Exception:
            self._logger.exception("Failed to delete payment id=%s", payment_id)
            raise
        return cursor.rowcount > 0

    def get_paid_total(self, rental_id: int) -> float:
        try:
            row = self._connection.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS paid_total
                FROM payments
                WHERE rental_id = ?
                """,
                (rental_id,),
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to calculate paid total rental_id=%s", rental_id
            )
            raise
        return float(row["paid_total"] or 0) if row else 0.0

    def get_total_received_by_period(self, start_date: str, end_date: str) -> float:
        try:
            row = self._connection.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total_received
                FROM payments
                WHERE paid_at IS NOT NULL
                  AND date(paid_at) >= ?
                  AND date(paid_at) <= ?
                """,
                (start_date, end_date),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to calculate total received by period")
            raise
        return float(row["total_received"] or 0) if row else 0.0
