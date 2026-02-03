"""Rental service for business rules."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Iterable, Optional

from rental_manager.domain.models import Rental, RentalItem, RentalStatus
from rental_manager.logging_config import get_logger
from rental_manager.repositories import payment_repo, rental_repo
from rental_manager.services.errors import NotFoundError, ValidationError
from rental_manager.services.inventory_service import InventoryService


class RentalService:
    """Service for rental business rules."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._inventory_service = InventoryService(connection)
        self._payment_repo = payment_repo.PaymentRepository(connection)
        self._logger = get_logger(self.__class__.__name__)

    def _items_for_validation(
        self, items: Iterable[dict[str, object]]
    ) -> list[tuple[int, int]]:
        aggregated: dict[int, int] = {}
        for item in items:
            product_id = int(item["product_id"])
            aggregated[product_id] = aggregated.get(product_id, 0) + int(item["qty"])
        return list(aggregated.items())

    def _items_from_rental_items(
        self, items: Iterable[RentalItem]
    ) -> list[tuple[int, int]]:
        aggregated: dict[int, int] = {}
        for item in items:
            aggregated[item.product_id] = aggregated.get(item.product_id, 0) + item.qty
        return list(aggregated.items())

    def _get_rental_with_items(self, rental_id: int) -> tuple[Rental, list[RentalItem]]:
        rental_data = rental_repo.get_rental_with_items(
            rental_id, connection=self._connection
        )
        if not rental_data:
            raise NotFoundError(f"Pedido {rental_id} não encontrado.")
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

    def _normalize_dates(self, start_date: str, end_date: str) -> tuple[str, str]:
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise ValidationError(
                "Datas inválidas. Verifique o início e o fim do pedido."
            ) from exc
        if end == start:
            end = start + timedelta(days=1)
            self._logger.info(
                "End_date ajustado para 1 dia após start_date (%s).", end.isoformat()
            )
        if end < start:
            raise ValidationError(
                "A data de término deve ser posterior à data de início."
            )
        return start.isoformat(), end.isoformat()

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
        start_date, end_date = self._normalize_dates(start_date, end_date)
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
        status: str | RentalStatus,
    ) -> Rental:
        start_date, end_date = self._normalize_dates(start_date, end_date)
        items_for_validation = self._items_for_validation(items)
        self._validate_inventory(
            items_for_validation,
            start_date,
            end_date,
            exclude_rental_id=rental_id,
        )
        paid_total = self._payment_repo.get_paid_total(rental_id)
        rental = rental_repo.update_rental(
            rental_id,
            customer_id,
            event_date,
            start_date,
            end_date,
            address,
            items,
            total_value,
            paid_total,
            status,
            connection=self._connection,
        )
        if not rental:
            raise NotFoundError(f"Pedido {rental_id} não encontrado.")
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
            raise NotFoundError(f"Pedido {rental_id} não encontrado.")
        return True

    def cancel_rental(self, rental_id: int) -> bool:
        updated = rental_repo.set_status(
            rental_id, RentalStatus.CANCELED, connection=self._connection
        )
        if not updated:
            raise NotFoundError(f"Pedido {rental_id} não encontrado.")
        return True

    def complete_rental(self, rental_id: int) -> bool:
        updated = rental_repo.set_status(
            rental_id, RentalStatus.COMPLETED, connection=self._connection
        )
        if not updated:
            raise NotFoundError(f"Pedido {rental_id} não encontrado.")
        return True
