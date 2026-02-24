"""Expense service for business rules."""

from __future__ import annotations

import sqlite3
from typing import Optional

from rental_manager.domain.models import Expense
from rental_manager.repositories.expense_repo import ExpenseRepo
from rental_manager.services.errors import NotFoundError, ValidationError


class ExpenseService:
    """Service for expense operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._repo = ExpenseRepo(connection)

    def list_expenses(self, start_date: str, end_date: str) -> list[Expense]:
        return self._repo.list_by_period(start_date, end_date)

    def list_categories(self) -> list[str]:
        return self._repo.list_categories()

    def get_total_by_period(self, start_date: str, end_date: str) -> float:
        return self._repo.get_total_by_period(start_date, end_date)

    def create_expense(
        self,
        date: str,
        category: Optional[str],
        description: Optional[str],
        amount: float,
        payment_method: Optional[str],
        supplier: Optional[str],
        notes: Optional[str],
    ) -> Expense:
        self._validate(date, amount)
        with self._connection:
            return self._repo.create(
                date=date,
                category=category,
                description=description,
                amount=amount,
                payment_method=payment_method,
                supplier=supplier,
                notes=notes,
            )

    def update_expense(
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
        self._validate(date, amount)
        existing = self._repo.get_by_id(expense_id)
        if not existing:
            raise NotFoundError("Despesa não encontrada.")
        with self._connection:
            return self._repo.update(
                expense_id=expense_id,
                date=date,
                category=category,
                description=description,
                amount=amount,
                payment_method=payment_method,
                supplier=supplier,
                notes=notes,
            )

    def delete_expense(self, expense_id: int) -> bool:
        existing = self._repo.get_by_id(expense_id)
        if not existing:
            raise NotFoundError("Despesa não encontrada.")
        with self._connection:
            return self._repo.delete(expense_id)

    def _validate(self, date: str, amount: float) -> None:
        if not date:
            raise ValidationError("A data da despesa é obrigatória.")
        if amount <= 0:
            raise ValidationError("O valor da despesa deve ser maior que zero.")
