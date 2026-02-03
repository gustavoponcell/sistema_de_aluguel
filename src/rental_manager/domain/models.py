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


@dataclass(slots=True)
class Payment:
    id: Optional[int]
    rental_id: int
    amount: float
    method: Optional[str]
    paid_at: Optional[str]
    note: Optional[str]


@dataclass(slots=True)
class Product:
    id: Optional[int]
    name: str
    category: Optional[str]
    total_qty: int
    unit_price: Optional[float]
    active: bool
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
    start_date: str
    end_date: str
    address: Optional[str]
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
