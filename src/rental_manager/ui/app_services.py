"""Service container for the UI layer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from rental_manager.repositories import CustomerRepo, ProductRepo
from rental_manager.services.inventory_service import InventoryService
from rental_manager.services.rental_service import RentalService


@dataclass(frozen=True)
class AppServices:
    """Shared repositories and services for dependency injection."""

    connection: sqlite3.Connection
    customer_repo: CustomerRepo
    product_repo: ProductRepo
    inventory_service: InventoryService
    rental_service: RentalService
