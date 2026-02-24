"""Repository for expense persistence."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from rental_manager.domain.models import Expense
from rental_manager.logging_config import get_logger
from rental_manager.repositories.mappers import expense_from_row


class ExpenseRepo:
    """Data access for expenses."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._logger = get_logger(self.__class__.__name__)

    def create(
        self,
        date: str,
        category: Optional[str],
        description: Optional[str],
        amount: float,
        payment_method: Optional[str],
        supplier: Optional[str],
        notes: Optional[str],
    ) -> Expense:
        created_at = datetime.now().isoformat(timespec="seconds")
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO expenses (
                    created_at,
                    date,
                    category,
                    description,
                    amount,
                    payment_method,
                    supplier,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    date,
                    category,
                    description,
                    amount,
                    payment_method,
                    supplier,
                    notes,
                ),
            )
        except Exception:
            self._logger.exception("Failed to create expense")
            raise
        return Expense(
            id=int(cursor.lastrowid),
            created_at=created_at,
            date=date,
            category=category,
            description=description,
            amount=amount,
            payment_method=payment_method,
            supplier=supplier,
            notes=notes,
        )

    def update(
        self,
        expense_id: int,
        date: str,
        category: Optional[str],
        description: Optional[str],
        amount: float,
        payment_method: Optional[str],
        supplier: Optional[str],
        notes: Optional[str],
    ) -> bool:
        try:
            cursor = self._connection.execute(
                """
                UPDATE expenses
                SET date = ?,
                    category = ?,
                    description = ?,
                    amount = ?,
                    payment_method = ?,
                    supplier = ?,
                    notes = ?
                WHERE id = ?
                """,
                (
                    date,
                    category,
                    description,
                    amount,
                    payment_method,
                    supplier,
                    notes,
                    expense_id,
                ),
            )
        except Exception:
            self._logger.exception("Failed to update expense id=%s", expense_id)
            raise
        return cursor.rowcount > 0

    def delete(self, expense_id: int) -> bool:
        try:
            cursor = self._connection.execute(
                "DELETE FROM expenses WHERE id = ?",
                (expense_id,),
            )
        except Exception:
            self._logger.exception("Failed to delete expense id=%s", expense_id)
            raise
        return cursor.rowcount > 0

    def get_by_id(self, expense_id: int) -> Optional[Expense]:
        try:
            row = self._connection.execute(
                "SELECT * FROM expenses WHERE id = ?",
                (expense_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch expense id=%s", expense_id)
            raise
        return expense_from_row(row) if row else None

    def list_by_period(self, start_date: str, end_date: str) -> list[Expense]:
        try:
            rows = self._connection.execute(
                """
                SELECT *
                FROM expenses
                WHERE date(date) >= ?
                  AND date(date) <= ?
                ORDER BY date(date) DESC, id DESC
                """,
                (start_date, end_date),
            ).fetchall()
        except Exception:
            self._logger.exception(
                "Failed to list expenses period=%s..%s", start_date, end_date
            )
            raise
        return [expense_from_row(row) for row in rows]

    def list_categories(self) -> list[str]:
        try:
            rows = self._connection.execute(
                """
                SELECT DISTINCT category
                FROM expenses
                WHERE category IS NOT NULL
                  AND trim(category) != ''
                ORDER BY category
                """
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to list expense categories")
            raise
        return [row["category"] for row in rows if row["category"]]

    def get_total_by_period(self, start_date: str, end_date: str) -> float:
        try:
            row = self._connection.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total_expenses
                FROM expenses
                WHERE date(date) >= ?
                  AND date(date) <= ?
                """,
                (start_date, end_date),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to calculate expense total by period")
            raise
        return float(row["total_expenses"] or 0) if row else 0.0
