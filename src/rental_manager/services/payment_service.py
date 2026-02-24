"""Payment service for business rules."""

from __future__ import annotations

import sqlite3
<<<<<<< HEAD
from datetime import datetime
=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
from typing import Optional

from rental_manager.domain.models import Payment, PaymentStatus
from rental_manager.repositories import payment_repo, rental_repo
from rental_manager.services.errors import NotFoundError, ValidationError


class PaymentService:
    """Service for payment operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._repo = payment_repo.PaymentRepository(connection)
<<<<<<< HEAD
        self._ensure_paid_at_defaults()
=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d

    def list_payments(self, rental_id: int) -> list[Payment]:
        return self._repo.list_by_rental(rental_id)

    def get_paid_total(self, rental_id: int) -> float:
        return self._repo.get_paid_total(rental_id)

    def add_payment(
        self,
        rental_id: int,
        amount: float,
        method: Optional[str],
        paid_at: Optional[str],
        note: Optional[str],
    ) -> Payment:
        if amount <= 0:
            raise ValidationError("O valor do pagamento deve ser maior que zero.")
<<<<<<< HEAD
        normalized_paid_at = self._normalize_paid_at(paid_at)
        with self._connection:
            payment = self._repo.create(rental_id, amount, method, normalized_paid_at, note)
=======
        with self._connection:
            payment = self._repo.create(rental_id, amount, method, paid_at, note)
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
            self._sync_rental_payment(rental_id)
        return payment

    def update_payment(
        self,
        payment_id: int,
        amount: float,
        method: Optional[str],
        paid_at: Optional[str],
        note: Optional[str],
    ) -> bool:
        if amount <= 0:
            raise ValidationError("O valor do pagamento deve ser maior que zero.")
        payment = self._repo.get_by_id(payment_id)
        if not payment:
            raise NotFoundError("Pagamento não encontrado.")
<<<<<<< HEAD
        normalized_paid_at = self._normalize_paid_at(paid_at)
        with self._connection:
            updated = self._repo.update(payment_id, amount, method, normalized_paid_at, note)
=======
        with self._connection:
            updated = self._repo.update(payment_id, amount, method, paid_at, note)
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
            self._sync_rental_payment(payment.rental_id)
        return updated

    def delete_payment(self, payment_id: int) -> bool:
        payment = self._repo.get_by_id(payment_id)
        if not payment:
            raise NotFoundError("Pagamento não encontrado.")
        with self._connection:
            deleted = self._repo.delete(payment_id)
            self._sync_rental_payment(payment.rental_id)
        return deleted

    def _sync_rental_payment(self, rental_id: int) -> None:
        rental_data = rental_repo.get_rental_with_items(
            rental_id, connection=self._connection
        )
        if not rental_data:
            raise NotFoundError(f"Aluguel {rental_id} não encontrado.")
        rental, _items = rental_data
        paid_total = self._repo.get_paid_total(rental_id)
        status = self._payment_status(paid_total, rental.total_value)
        rental_repo.set_payment(
            rental_id,
            paid_total,
            status,
            connection=self._connection,
        )

<<<<<<< HEAD
    def _normalize_paid_at(self, paid_at: Optional[str]) -> str:
        if paid_at and paid_at.strip():
            return paid_at
        return datetime.now().isoformat(timespec="seconds")

    def _ensure_paid_at_defaults(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE payments
                SET paid_at = (
                    SELECT COALESCE(
                        r.updated_at,
                        CASE
                            WHEN r.event_date IS NOT NULL THEN r.event_date || ' 00:00:00'
                            ELSE datetime('now')
                        END
                    )
                    FROM rentals r
                    WHERE r.id = payments.rental_id
                )
                WHERE paid_at IS NULL
                """
            )

=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
    def _payment_status(self, paid_value: float, total_value: float) -> PaymentStatus:
        if paid_value <= 0:
            return PaymentStatus.UNPAID
        if paid_value < total_value:
            return PaymentStatus.PARTIAL
        return PaymentStatus.PAID
