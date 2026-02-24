"""Helpers used by assistant flows to talk to services only."""

from __future__ import annotations

from typing import Optional, Sequence

from rental_manager.domain.models import (
    Customer,
    Expense,
    Payment,
    Product,
    Rental,
    RentalStatus,
)
from rental_manager.repositories.rental_repo import FinanceReport, RentalFinanceRow
from rental_manager.ui.app_services import AppServices


class FlowServiceAdapter:
    """Adapter that exposes only service-layer calls for flows."""

    def __init__(self, services: AppServices) -> None:
        self._services = services

    # ------------------------------------------------------------------ helpers
    def _notify(self, *categories: str) -> None:
        categories = categories or ("global",)
        for category in categories:
            self._services.data_bus.emit_change(category)

    # ------------------------------------------------------------------ reads
    def list_customers(self, term: str | None = None) -> list[Customer]:
        customer_service = self._services.customer_service
        if term:
            return customer_service.search_customers(term)
        return customer_service.list_customers()

    def list_customers_by_period(self, start: str, end: str) -> list[Customer]:
        return self._services.customer_service.list_by_period(start, end)

    def list_products(self) -> list[Product]:
        return self._services.product_service.list_active_products()

    def list_rental_rows(
        self,
        *,
        start_date: str,
        end_date: str,
        statuses: Optional[Sequence[RentalStatus]] = None,
        search: Optional[str] = None,
    ) -> list[RentalFinanceRow]:
        rows = self._services.rental_service.list_finance_details(
            start_date,
            end_date,
        )
        normalized_statuses = (
            {status if isinstance(status, RentalStatus) else RentalStatus(status) for status in statuses}
            if statuses
            else None
        )
        if normalized_statuses:
            rows = [row for row in rows if row.status in normalized_statuses]
        if search:
            lowered = search.lower()
            rows = [
                row
                for row in rows
                if lowered in row.customer_name.lower()
                or lowered in str(row.id)
            ]
        return rows

    def list_agenda_rows(
        self, start_date: str, end_date: str
    ) -> list[RentalFinanceRow]:
        return self._services.rental_service.list_agenda_rows(start_date, end_date)

    def get_finance_report(self, start: str, end: str) -> FinanceReport:
        return self._services.rental_service.get_finance_report(start, end)

    def list_finance_details(
        self, start: str, end: str
    ) -> list[RentalFinanceRow]:
        return self._services.rental_service.list_finance_details(start, end)

    def list_customer_history(
        self, customer_id: int, start: str, end: str
    ) -> list[Rental]:
        return self._services.rental_service.list_customer_history(
            customer_id,
            start,
            end,
        )

    # ------------------------------------------------------------------ writes
    def create_draft_order(self, **kwargs) -> Rental:
        rental = self._services.rental_service.create_draft_rental(**kwargs)
        self._notify("rentals", "inventory")
        return rental

    def complete_rental(self, rental_id: int) -> None:
        self._services.rental_service.complete_rental(rental_id)
        self._notify("rentals", "inventory")

    def register_payment(self, **kwargs) -> Payment:
        payment = self._services.payment_service.add_payment(**kwargs)
        self._notify("payments", "rentals")
        return payment

    def register_expense(self, **kwargs) -> Expense:
        expense = self._services.expense_service.create_expense(**kwargs)
        self._notify("expenses")
        return expense

    def update_stock(self, product_id: int, total_qty: int) -> Product:
        product = self._services.product_service.update_total_quantity(
            product_id,
            total_qty,
        )
        self._notify("products", "inventory")
        return product

    def create_customer(
        self, *, name: str, phone: str | None, notes: str | None
    ) -> Customer:
        customer = self._services.customer_service.create_customer(
            name=name,
            phone=phone,
            notes=notes,
        )
        self._notify("customers")
        return customer
