"""Service container for the UI layer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
<<<<<<< HEAD
from pathlib import Path

from rental_manager.repositories import CustomerRepo, DocumentRepository, ProductRepo
from rental_manager.services.customer_service import CustomerService
from rental_manager.services.document_service import DocumentService
=======

from rental_manager.repositories import CustomerRepo, DocumentRepository, ProductRepo
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
from rental_manager.services.expense_service import ExpenseService
from rental_manager.services.inventory_service import InventoryService
from rental_manager.services.order_service import OrderService
from rental_manager.services.payment_service import PaymentService
<<<<<<< HEAD
from rental_manager.services.product_service import ProductService
=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
from rental_manager.services.rental_service import RentalService
from rental_manager.ui.data_bus import DataEventBus
from rental_manager.utils.theme import ThemeManager


@dataclass(frozen=True)
class AppServices:
    """Shared repositories and services for dependency injection."""

    connection: sqlite3.Connection
<<<<<<< HEAD
    config_path: Path
=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
    data_bus: DataEventBus
    customer_repo: CustomerRepo
    document_repo: DocumentRepository
    product_repo: ProductRepo
<<<<<<< HEAD
    customer_service: CustomerService
    document_service: DocumentService
    product_service: ProductService
=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
    inventory_service: InventoryService
    order_service: OrderService
    rental_service: RentalService
    payment_service: PaymentService
    expense_service: ExpenseService
    theme_manager: ThemeManager
