"""Rental service for business rules."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Iterable, Optional

from rental_manager.db.connection import transaction
from rental_manager.domain.models import Rental, RentalItem, RentalStatus
from rental_manager.logging_config import get_logger
from rental_manager.repositories import payment_repo, rental_repo
from rental_manager.services.errors import NotFoundError, ValidationError
from rental_manager.services.order_service import OrderService


class RentalService:
    """Service for rental business rules."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._order_service = OrderService(connection)
        self._payment_repo = payment_repo.PaymentRepository(connection)
        self._logger = get_logger(self.__class__.__name__)

    def _get_rental_with_items(self, rental_id: int) -> tuple[Rental, list[RentalItem]]:
        rental_data = rental_repo.get_rental_with_items(
            rental_id, connection=self._connection
        )
        if not rental_data:
            raise NotFoundError(f"Pedido {rental_id} não encontrado.")
        return rental_data

    def _normalize_dates(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        if not start_date or not end_date:
            return None, None
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
        start_date: Optional[str],
        end_date: Optional[str],
        address: Optional[str],
        contact_phone: Optional[str],
        delivery_required: bool,
        items: Iterable[dict[str, object]],
        total_value: Optional[float] = None,
        paid_value: float = 0.0,
    ) -> Rental:
        start_date, end_date = self._normalize_dates(start_date, end_date)
        try:
            self._order_service.validate_availability(
                items,
                start_date=start_date,
                end_date=end_date,
            )
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return rental_repo.create_rental(
            customer_id,
            event_date,
            start_date,
            end_date,
            address,
            contact_phone,
            delivery_required,
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
        start_date: Optional[str],
        end_date: Optional[str],
        address: Optional[str],
        contact_phone: Optional[str],
        delivery_required: bool,
        items: Iterable[dict[str, object]],
        total_value: Optional[float],
        status: str | RentalStatus,
    ) -> Rental:
        start_date, end_date = self._normalize_dates(start_date, end_date)
        try:
            self._order_service.validate_availability(
                items,
                start_date=start_date,
                end_date=end_date,
                exclude_rental_id=rental_id,
            )
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        paid_total = self._payment_repo.get_paid_total(rental_id)
        rental = rental_repo.update_rental(
            rental_id,
            customer_id,
            event_date,
            start_date,
            end_date,
            address,
            contact_phone,
            delivery_required,
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
        try:
            self._order_service.validate_availability(
                items,
                start_date=rental.start_date,
                end_date=rental.end_date,
                exclude_rental_id=rental_id,
            )
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
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
        rental, items = self._get_rental_with_items(rental_id)
        if rental.status == RentalStatus.COMPLETED:
            return True
        with transaction(self._connection):
            self._order_service.apply_sale_stock_deduction(
                items, exclude_rental_id=rental_id
            )
            updated = rental_repo.set_status(
                rental_id, RentalStatus.COMPLETED, connection=self._connection
            )
        if not updated:
            raise NotFoundError(f"Pedido {rental_id} não encontrado.")
        return True
