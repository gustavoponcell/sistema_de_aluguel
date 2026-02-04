"""SQLite row mappers for domain models."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

from rental_manager.domain.models import (
    Customer,
    Document,
    DocumentType,
    Expense,
    Payment,
    PaymentStatus,
    Product,
    ProductKind,
    Rental,
    RentalItem,
    RentalStatus,
)


def _row_value(row: sqlite3.Row, key: str) -> Any:
    return row[key] if key in row.keys() else None


def product_from_row(row: sqlite3.Row) -> Product:
    raw_kind = _row_value(row, "kind") or ProductKind.RENTAL.value
    try:
        kind = ProductKind(raw_kind)
    except ValueError:
        kind = ProductKind.RENTAL
    return Product(
        id=_row_value(row, "id"),
        name=row["name"],
        category=_row_value(row, "category"),
        total_qty=row["total_qty"],
        unit_price=_row_value(row, "unit_price"),
        kind=kind,
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
        "kind": product.kind.value if isinstance(product.kind, ProductKind) else product.kind,
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
        start_date=_row_value(row, "start_date"),
        end_date=_row_value(row, "end_date"),
        address=_row_value(row, "address"),
        contact_phone=_row_value(row, "contact_phone"),
        delivery_required=bool(_row_value(row, "delivery_required") or 0),
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
        "contact_phone": rental.contact_phone,
        "delivery_required": int(rental.delivery_required),
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


def payment_from_row(row: sqlite3.Row) -> Payment:
    return Payment(
        id=_row_value(row, "id"),
        rental_id=row["rental_id"],
        amount=row["amount"],
        method=_row_value(row, "method"),
        paid_at=_row_value(row, "paid_at"),
        note=_row_value(row, "note"),
    )


def payment_to_record(payment: Payment) -> Dict[str, Any]:
    return {
        "id": payment.id,
        "rental_id": payment.rental_id,
        "amount": payment.amount,
        "method": payment.method,
        "paid_at": payment.paid_at,
        "note": payment.note,
    }


def expense_from_row(row: sqlite3.Row) -> Expense:
    return Expense(
        id=_row_value(row, "id"),
        created_at=_row_value(row, "created_at"),
        date=row["date"],
        category=_row_value(row, "category"),
        description=_row_value(row, "description"),
        amount=row["amount"],
        payment_method=_row_value(row, "payment_method"),
        supplier=_row_value(row, "supplier"),
        notes=_row_value(row, "notes"),
    )


def expense_to_record(expense: Expense) -> Dict[str, Any]:
    return {
        "id": expense.id,
        "created_at": expense.created_at,
        "date": expense.date,
        "category": expense.category,
        "description": expense.description,
        "amount": expense.amount,
        "payment_method": expense.payment_method,
        "supplier": expense.supplier,
        "notes": expense.notes,
    }


def document_from_row(row: sqlite3.Row) -> Document:
    return Document(
        id=_row_value(row, "id"),
        created_at=row["created_at"],
        doc_type=DocumentType(row["type"]),
        customer_name=row["customer_name"],
        reference_date=_row_value(row, "reference_date"),
        file_name=row["file_name"],
        file_path=row["file_path"],
        order_id=_row_value(row, "order_id"),
        notes=_row_value(row, "notes"),
    )
