"""Rental service for business rules."""

from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from rental_manager.domain.models import PaymentStatus, Rental, RentalItem, RentalStatus
from rental_manager.logging_config import get_logger
from rental_manager.repositories import rental_repo
from rental_manager.services.errors import NotFoundError, ValidationError
from rental_manager.services.inventory_service import InventoryService


class RentalService:
    """Service for rental business rules."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._inventory_service = InventoryService(connection)
        self._logger = get_logger(self.__class__.__name__)

    def _items_for_validation(
        self, items: Iterable[dict[str, object]]
    ) -> list[tuple[int, int]]:
        return [(int(item["product_id"]), int(item["qty"])) for item in items]

    def _items_from_rental_items(
        self, items: Iterable[RentalItem]
    ) -> list[tuple[int, int]]:
        return [(item.product_id, item.qty) for item in items]

    def _get_rental_with_items(self, rental_id: int) -> tuple[Rental, list[RentalItem]]:
        rental_data = rental_repo.get_rental_with_items(
            rental_id, connection=self._connection
        )
        if not rental_data:
            raise NotFoundError(f"Aluguel {rental_id} não encontrado.")
        return rental_data

    def _validate_inventory(
        self,
        items: Iterable[tuple[int, int]],
        start_date: str,
        end_date: str,
        *,
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        try:
            self._inventory_service.validate_request(
                items,
                start_date,
                end_date,
                exclude_rental_id=exclude_rental_id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def create_draft_rental(
        self,
        customer_id: int,
        event_date: str,
        start_date: str,
        end_date: str,
        address: Optional[str],
        items: Iterable[dict[str, object]],
        total_value: Optional[float] = None,
        paid_value: float = 0.0,
    ) -> Rental:
        items_for_validation = self._items_for_validation(items)
        self._validate_inventory(items_for_validation, start_date, end_date)
        return rental_repo.create_rental(
            customer_id,
            event_date,
            start_date,
            end_date,
            address,
            items,
            total_value,
            paid_value=paid_value,
            status=RentalStatus.DRAFT,
            connection=self._connection,
        )

    def update_rental(
        self,
        rental_id: int,
        customer_id: int,
        event_date: str,
        start_date: str,
        end_date: str,
        address: Optional[str],
        items: Iterable[dict[str, object]],
        total_value: Optional[float],
        paid_value: float,
        status: str | RentalStatus,
    ) -> Rental:
        items_for_validation = self._items_for_validation(items)
        self._validate_inventory(
            items_for_validation,
            start_date,
            end_date,
            exclude_rental_id=rental_id,
        )
        rental = rental_repo.update_rental(
            rental_id,
            customer_id,
            event_date,
            start_date,
            end_date,
            address,
            items,
            total_value,
            paid_value,
            status,
            connection=self._connection,
        )
        if not rental:
            raise NotFoundError(f"Aluguel {rental_id} não encontrado.")
        return rental

    def confirm_rental(self, rental_id: int) -> bool:
        rental, items = self._get_rental_with_items(rental_id)
        items_for_validation = self._items_from_rental_items(items)
        self._validate_inventory(
            items_for_validation,
            rental.start_date,
            rental.end_date,
            exclude_rental_id=rental_id,
        )
        updated = rental_repo.set_status(
            rental_id, RentalStatus.CONFIRMED, connection=self._connection
        )
        if not updated:
            raise NotFoundError(f"Aluguel {rental_id} não encontrado.")
        return True

    def cancel_rental(self, rental_id: int) -> bool:
        updated = rental_repo.set_status(
            rental_id, RentalStatus.CANCELED, connection=self._connection
        )
        if not updated:
            raise NotFoundError(f"Aluguel {rental_id} não encontrado.")
        return True

    def complete_rental(self, rental_id: int) -> bool:
        updated = rental_repo.set_status(
            rental_id, RentalStatus.COMPLETED, connection=self._connection
        )
        if not updated:
            raise NotFoundError(f"Aluguel {rental_id} não encontrado.")
        return True

    def set_payment(self, rental_id: int, paid_value: float) -> bool:
        rental, _items = self._get_rental_with_items(rental_id)
        payment_status = self._compute_payment_status(paid_value, rental.total_value)
        updated = rental_repo.set_payment(
            rental_id,
            paid_value,
            payment_status,
            connection=self._connection,
        )
        if not updated:
            raise NotFoundError(f"Aluguel {rental_id} não encontrado.")
        return True

    def _compute_payment_status(
        self, paid_value: float, total_value: float
    ) -> PaymentStatus:
        if paid_value <= 0:
            return PaymentStatus.UNPAID
        if paid_value < total_value:
            return PaymentStatus.PARTIAL
        return PaymentStatus.PAID
