"""Domain dataclasses and enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RentalStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"
    COMPLETED = "completed"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class DocumentType(str, Enum):
    CONTRACT = "contract"
    RECEIPT = "receipt"


class ProductKind(str, Enum):
    RENTAL = "rental"
    SALE = "sale"
    SERVICE = "service"


SERVICE_DEFAULT_QTY = 999


@dataclass(slots=True)
class Payment:
    id: Optional[int]
    rental_id: int
    amount: float
    method: Optional[str]
    paid_at: Optional[str]
    note: Optional[str]


@dataclass(slots=True)
class Expense:
    id: Optional[int]
    created_at: Optional[str]
    date: str
    category: Optional[str]
    description: Optional[str]
    amount: float
    payment_method: Optional[str]
    supplier: Optional[str]
    notes: Optional[str]


@dataclass(slots=True)
class Product:
    id: Optional[int]
    name: str
    category: Optional[str]
    total_qty: int
    unit_price: Optional[float]
    active: bool
    kind: ProductKind = ProductKind.RENTAL
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(slots=True)
class Customer:
    id: Optional[int]
    name: str
    phone: Optional[str]
    notes: Optional[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(slots=True)
class Rental:
    id: Optional[int]
    customer_id: int
    event_date: str
    start_date: Optional[str]
    end_date: Optional[str]
    address: Optional[str]
    contact_phone: Optional[str] = None
    delivery_required: bool = False
    status: RentalStatus
    total_value: float
    paid_value: float
    payment_status: PaymentStatus
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(slots=True)
class RentalItem:
    id: Optional[int]
    rental_id: int
    product_id: int
    qty: int
    unit_price: float
    line_total: float
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(slots=True)
class Document:
    id: Optional[int]
    rental_id: int
    doc_type: DocumentType
    file_path: str
    generated_at: str
    checksum: str
