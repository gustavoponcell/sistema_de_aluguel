"""Customer service bridging UI and repository."""

from __future__ import annotations

import sqlite3
from typing import List

from rental_manager.domain.models import Customer
from rental_manager.repositories.customer_repo import CustomerRepo
from rental_manager.services.errors import NotFoundError, ValidationError


class CustomerService:
    """Business layer for customer operations."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        repo: CustomerRepo | None = None,
    ) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._repo = repo or CustomerRepo(connection)

    def list_customers(self) -> List[Customer]:
        """Return all customers ordered by name."""
        return self._repo.list_all()

    def search_customers(self, term: str) -> List[Customer]:
        """Search customers by name."""
        return self._repo.search_by_name(term)

    def list_by_period(self, start_date: str, end_date: str) -> List[Customer]:
        """List customers created between two dates (inclusive)."""
        return self._repo.list_by_period(start_date, end_date)

    def create_customer(
        self, *, name: str, phone: str | None, notes: str | None
    ) -> Customer:
        """Create a new customer record."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("O nome do cliente é obrigatório.")
        return self._repo.create(
            name=cleaned_name,
            phone=(phone or "").strip() or None,
            notes=(notes or "").strip() or None,
        )

    def get_customer(self, customer_id: int) -> Customer:
        """Fetch a customer or raise if missing."""
        customer = self._repo.get_by_id(customer_id)
        if not customer:
            raise NotFoundError("Cliente não encontrado.")
        return customer

    def update_customer(
        self,
        customer_id: int,
        *,
        name: str,
        phone: str | None,
        notes: str | None,
    ) -> Customer:
        """Update an existing customer."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("O nome do cliente é obrigatório.")
        updated = self._repo.update(
            customer_id=customer_id,
            name=cleaned_name,
            phone=(phone or "").strip() or None,
            notes=(notes or "").strip() or None,
        )
        if not updated:
            raise NotFoundError("Cliente não encontrado.")
        return updated

    def delete_customer(self, customer_id: int) -> None:
        """Delete a customer by id."""
        deleted = self._repo.delete(customer_id)
        if not deleted:
            raise NotFoundError("Cliente não encontrado.")
