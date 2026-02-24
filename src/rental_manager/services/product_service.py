"""Product service exposing inventory friendly helpers."""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from rental_manager.domain.models import Product, ProductKind
from rental_manager.repositories.product_repo import ProductRepo
from rental_manager.services.errors import NotFoundError, ValidationError


class ProductService:
    """Business layer for product operations used by flows and screens."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        repo: ProductRepo | None = None,
    ) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._repo = repo or ProductRepo(connection)

    # ------------------------------------------------------------------ queries
    def list_active_products(self) -> List[Product]:
        """Return currently active products ordered by name."""
        return self._repo.list_active()

    def list_all_products(self) -> List[Product]:
        """Return all products regardless of active flag."""
        return self._repo.list_all()

    def search_products(
        self, term: str, *, include_inactive: bool = False
    ) -> List[Product]:
        """Search products by name."""
        return self._repo.search_by_name(term, include_inactive=include_inactive)

    def get_product(self, product_id: int) -> Product:
        """Fetch a product or raise if missing."""
        product = self._repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Produto não encontrado.")
        return product

    # ------------------------------------------------------------------ commands
    def create_product(
        self,
        *,
        name: str,
        category: Optional[str],
        total_qty: int,
        unit_price: Optional[float],
        kind: ProductKind,
        active: bool = True,
    ) -> Product:
        """Create a new product with validation."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("O nome do item é obrigatório.")
        cleaned_category = (category or "").strip()
        if not cleaned_category:
            raise ValidationError("A categoria do item é obrigatória.")
        normalized_kind = kind if isinstance(kind, ProductKind) else ProductKind(kind)
        self._validate_quantities(normalized_kind, total_qty)
        price = self._normalize_price(unit_price)
        return self._repo.create(
            cleaned_name,
            cleaned_category,
            total_qty,
            price,
            normalized_kind,
            active,
        )

    def update_product(
        self,
        product_id: int,
        *,
        name: str,
        category: Optional[str],
        total_qty: int,
        unit_price: Optional[float],
        kind: ProductKind,
        active: bool = True,
    ) -> Product:
        """Update an existing product."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("O nome do item é obrigatório.")
        cleaned_category = (category or "").strip()
        if not cleaned_category:
            raise ValidationError("A categoria do item é obrigatória.")
        normalized_kind = kind if isinstance(kind, ProductKind) else ProductKind(kind)
        self._validate_quantities(normalized_kind, total_qty)
        price = self._normalize_price(unit_price)
        updated = self._repo.update(
            product_id=product_id,
            name=cleaned_name,
            category=cleaned_category,
            total_qty=total_qty,
            unit_price=price,
            kind=normalized_kind,
            active=active,
        )
        if not updated:
            raise NotFoundError("Produto não encontrado.")
        return updated

    def update_total_quantity(self, product_id: int, total_qty: int) -> Product:
        """Update product total quantity (stock adjustment)."""
        product = self.get_product(product_id)
        self._validate_quantities(product.kind, total_qty)
        updated = self._repo.update(
            product_id=product_id,
            name=product.name,
            category=product.category,
            total_qty=total_qty,
            unit_price=product.unit_price,
            kind=product.kind,
            active=product.active,
        )
        if not updated:
            raise NotFoundError("Produto não encontrado.")
        return updated

    def deactivate_product(self, product_id: int) -> None:
        """Soft delete a product."""
        success = self._repo.soft_delete(product_id)
        if not success:
            raise NotFoundError("Produto não encontrado.")

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _validate_quantities(kind: ProductKind, total_qty: int) -> None:
        if kind == ProductKind.SERVICE:
            return
        if total_qty <= 0:
            raise ValidationError("A quantidade deve ser maior que zero.")

    @staticmethod
    def _normalize_price(unit_price: Optional[float]) -> Optional[float]:
        if unit_price is None:
            return None
        if unit_price < 0:
            raise ValidationError("O preço não pode ser negativo.")
        return round(float(unit_price), 2)
