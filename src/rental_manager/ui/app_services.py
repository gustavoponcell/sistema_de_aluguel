"""Service container for the UI layer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from rental_manager.repositories import CustomerRepo, DocumentRepository, ProductRepo
from rental_manager.services.inventory_service import InventoryService
from rental_manager.services.payment_service import PaymentService
from rental_manager.services.rental_service import RentalService
from rental_manager.ui.data_bus import DataEventBus
from rental_manager.utils.theme import ThemeManager


@dataclass(frozen=True)
class AppServices:
    """Shared repositories and services for dependency injection."""

    connection: sqlite3.Connection
    data_bus: DataEventBus
    customer_repo: CustomerRepo
    document_repo: DocumentRepository
    product_repo: ProductRepo
    inventory_service: InventoryService
    rental_service: RentalService
    payment_service: PaymentService
    theme_manager: ThemeManager
