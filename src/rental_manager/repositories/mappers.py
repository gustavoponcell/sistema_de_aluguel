"""SQLite row mappers for domain models."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

from rental_manager.domain.models import (
    Customer,
    PaymentStatus,
    Product,
    Rental,
    RentalItem,
    RentalStatus,
)


def _row_value(row: sqlite3.Row, key: str) -> Any:
    return row[key] if key in row.keys() else None


def product_from_row(row: sqlite3.Row) -> Product:
    return Product(
        id=_row_value(row, "id"),
        name=row["name"],
        category=_row_value(row, "category"),
        total_qty=row["total_qty"],
        unit_price=_row_value(row, "unit_price"),
        active=bool(row["active"]),
        created_at=_row_value(row, "created_at"),
        updated_at=_row_value(row, "updated_at"),
    )


def product_to_record(product: Product) -> Dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "total_qty": product.total_qty,
        "unit_price": product.unit_price,
        "active": int(product.active),
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def customer_from_row(row: sqlite3.Row) -> Customer:
    return Customer(
        id=_row_value(row, "id"),
        name=row["name"],
        phone=_row_value(row, "phone"),
        notes=_row_value(row, "notes"),
        created_at=_row_value(row, "created_at"),
        updated_at=_row_value(row, "updated_at"),
    )


def customer_to_record(customer: Customer) -> Dict[str, Any]:
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "notes": customer.notes,
        "created_at": customer.created_at,
        "updated_at": customer.updated_at,
    }


def rental_from_row(row: sqlite3.Row) -> Rental:
    return Rental(
        id=_row_value(row, "id"),
        customer_id=row["customer_id"],
        event_date=row["event_date"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        address=_row_value(row, "address"),
        status=RentalStatus(row["status"]),
        total_value=row["total_value"],
        paid_value=row["paid_value"],
        payment_status=PaymentStatus(row["payment_status"]),
        created_at=_row_value(row, "created_at"),
        updated_at=_row_value(row, "updated_at"),
    )


def rental_to_record(rental: Rental) -> Dict[str, Any]:
    return {
        "id": rental.id,
        "customer_id": rental.customer_id,
        "event_date": rental.event_date,
        "start_date": rental.start_date,
        "end_date": rental.end_date,
        "address": rental.address,
        "status": rental.status.value,
        "total_value": rental.total_value,
        "paid_value": rental.paid_value,
        "payment_status": rental.payment_status.value,
        "created_at": rental.created_at,
        "updated_at": rental.updated_at,
    }


def rental_item_from_row(row: sqlite3.Row) -> RentalItem:
    return RentalItem(
        id=_row_value(row, "id"),
        rental_id=row["rental_id"],
        product_id=row["product_id"],
        qty=row["qty"],
        unit_price=row["unit_price"],
        line_total=row["line_total"],
        created_at=_row_value(row, "created_at"),
        updated_at=_row_value(row, "updated_at"),
    )


def rental_item_to_record(rental_item: RentalItem) -> Dict[str, Any]:
    return {
        "id": rental_item.id,
        "rental_id": rental_item.rental_id,
        "product_id": rental_item.product_id,
        "qty": rental_item.qty,
        "unit_price": rental_item.unit_price,
        "line_total": rental_item.line_total,
        "created_at": rental_item.created_at,
        "updated_at": rental_item.updated_at,
    }
