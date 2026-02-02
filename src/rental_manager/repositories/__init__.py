"""Repositories for data access."""

from rental_manager.repositories.customer_repo import CustomerRepo
from rental_manager.repositories.mappers import (
    customer_from_row,
    customer_to_record,
    product_from_row,
    product_to_record,
    rental_from_row,
    rental_item_from_row,
    rental_item_to_record,
    rental_to_record,
)
from rental_manager.repositories.product_repo import ProductRepo

__all__ = [
    "CustomerRepo",
    "customer_from_row",
    "customer_to_record",
    "ProductRepo",
    "product_from_row",
    "product_to_record",
    "rental_from_row",
    "rental_item_from_row",
    "rental_item_to_record",
    "rental_to_record",
]
