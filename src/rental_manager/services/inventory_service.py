"""Inventory availability calculations."""

from __future__ import annotations

import sqlite3
<<<<<<< HEAD
import time
from collections import defaultdict
=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
from datetime import date, timedelta
from typing import Iterable, Optional

from dateutil import parser

from rental_manager.domain.models import ProductKind, RentalStatus, SERVICE_DEFAULT_QTY
from rental_manager.logging_config import get_logger


def _to_iso_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return parser.isoparse(value).date().isoformat()


<<<<<<< HEAD
def _ensure_date_obj(value: str | date | None) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return parser.isoparse(value).date()
    except (TypeError, ValueError):
        return None


=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
RENTAL_BLOCKING_STATUSES = (
    RentalStatus.DRAFT.value,
    RentalStatus.CONFIRMED.value,
)

SALE_BLOCKING_STATUSES = (
    RentalStatus.DRAFT.value,
    RentalStatus.CONFIRMED.value,
)


class InventoryService:
    """Service for inventory availability checks."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._logger = get_logger(self.__class__.__name__)

    def get_reserved_qty(
        self,
        product_id: int,
        start_date: str | date,
        end_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        start_date = _to_iso_date(start_date)
        end_date = _to_iso_date(end_date)
        status_placeholders = ", ".join(["?"] * len(RENTAL_BLOCKING_STATUSES))
        params: list[object] = [
            product_id,
            ProductKind.RENTAL.value,
            *RENTAL_BLOCKING_STATUSES,
            end_date,
            start_date,
        ]
        exclude_clause = ""
        if exclude_rental_id is not None:
            exclude_clause = "AND r.id <> ?"
            params.append(exclude_rental_id)
        try:
            row = self._connection.execute(
                f"""
                SELECT COALESCE(SUM(ri.qty), 0) AS reserved_qty
                FROM rental_items ri
                JOIN rentals r ON r.id = ri.rental_id
                JOIN products p ON p.id = ri.product_id
                WHERE ri.product_id = ?
                  AND p.kind = ?
                  AND r.status IN ({status_placeholders})
                  AND r.start_date < ?
                  AND r.end_date > ?
                  {exclude_clause}
                """,
                params,
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch reserved qty for product_id=%s", product_id
            )
            raise
        return int(row["reserved_qty"]) if row else 0

    def get_available_qty(
        self,
        product_id: int,
        start_date: str | date,
        end_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        try:
            product_row = self._connection.execute(
                "SELECT total_qty, kind FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch product for id=%s", product_id)
            raise
        if not product_row:
            raise ValueError(f"Item {product_id} não encontrado.")
        total_qty = int(product_row["total_qty"])
        kind = product_row["kind"] if "kind" in product_row.keys() else None
        if kind == ProductKind.SERVICE.value:
            total_qty = max(total_qty, SERVICE_DEFAULT_QTY)
        if kind == ProductKind.SALE.value:
            return self.get_sale_available_qty(
                product_id, exclude_rental_id=exclude_rental_id
            )
        reserved_qty = self.get_reserved_qty(
            product_id,
            start_date,
            end_date,
            exclude_rental_id=exclude_rental_id,
        )
        return max(total_qty - reserved_qty, 0)

    def on_loan(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        ref_date = _to_iso_date(reference_date)
        status_placeholders = ", ".join(["?"] * len(RENTAL_BLOCKING_STATUSES))
        params: list[object] = [
            product_id,
            ProductKind.RENTAL.value,
            *RENTAL_BLOCKING_STATUSES,
            ref_date,
            ref_date,
        ]
        exclude_clause = ""
        if exclude_rental_id is not None:
            exclude_clause = "AND r.id <> ?"
            params.append(exclude_rental_id)
        try:
            row = self._connection.execute(
                f"""
                SELECT COALESCE(SUM(ri.qty), 0) AS reserved_qty
                FROM rental_items ri
                JOIN rentals r ON r.id = ri.rental_id
                JOIN products p ON p.id = ri.product_id
                WHERE ri.product_id = ?
                  AND p.kind = ?
                  AND r.status IN ({status_placeholders})
                  AND r.start_date <= ?
                  AND r.end_date > ?
                  {exclude_clause}
                """,
                params,
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch reserved qty on date for product_id=%s", product_id
            )
            raise
        return int(row["reserved_qty"]) if row else 0

    def available(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        try:
            product_row = self._connection.execute(
                "SELECT total_qty, kind FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch product for id=%s", product_id)
            raise
        if not product_row:
            raise ValueError(f"Item {product_id} não encontrado.")
        total_qty = int(product_row["total_qty"])
        kind = product_row["kind"] if "kind" in product_row.keys() else None
        if kind == ProductKind.SERVICE.value:
            total_qty = max(total_qty, SERVICE_DEFAULT_QTY)
        if kind == ProductKind.SALE.value:
            return self.get_sale_available_qty(
                product_id, exclude_rental_id=exclude_rental_id
            )
        reserved_qty = self.on_loan(
            product_id,
            reference_date,
            exclude_rental_id=exclude_rental_id,
        )
        return max(total_qty - reserved_qty, 0)

    def get_reserved_qty_on_date(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        return self.on_loan(
            product_id,
            reference_date,
            exclude_rental_id=exclude_rental_id,
        )

    def get_available_qty_on_date(
        self,
        product_id: int,
        reference_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> int:
        return self.available(
            product_id,
            reference_date,
            exclude_rental_id=exclude_rental_id,
        )

    def validate_request(
        self,
        items: Iterable[tuple[int, int]],
        start_date: str | date,
        end_date: str | date,
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        self.validate_rental_availability(
            rental_id=exclude_rental_id,
            items=items,
            start_date=start_date,
            end_date=end_date,
        )

    def validate_rental_availability(
        self,
        rental_id: Optional[int],
        items: Iterable[tuple[int, int]],
        start_date: str | date,
        end_date: str | date,
    ) -> None:
<<<<<<< HEAD
        range_start = _ensure_date_obj(start_date)
        range_end = _ensure_date_obj(end_date)
        if range_start is None or range_end is None:
            raise ValueError("Informe datas válidas para o período do pedido.")
        if range_end <= range_start:
=======
        start = date.fromisoformat(_to_iso_date(start_date))
        end = date.fromisoformat(_to_iso_date(end_date))
        if end <= start:
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
            raise ValueError(
                "Não foi possível salvar: a data de término deve ser posterior à data de início."
            )
        aggregated_items = self._aggregate_items(items)
<<<<<<< HEAD
        if not aggregated_items:
            return
        product_details = self._load_product_details(
            [product_id for product_id, _ in aggregated_items]
        )
        rental_products: list[int] = []
        sale_products: list[int] = []
        for product_id, _qty in aggregated_items:
            product = product_details.get(product_id)
            if not product:
                raise ValueError(f"Item {product_id} não encontrado.")
            kind = ProductKind(product["kind"])
            if kind == ProductKind.RENTAL:
                rental_products.append(product_id)
            elif kind == ProductKind.SALE:
                sale_products.append(product_id)
        conflicts = self._fetch_conflicting_reservations(
            rental_products,
            range_start,
            range_end,
            exclude_rental_id=rental_id,
        )
        conflicts_by_product: dict[int, list[tuple[date, date, int]]] = defaultdict(list)
        for row in conflicts:
            conflicts_by_product[int(row["product_id"])].append(
                (
                    row["start_date"],
                    row["end_date"],
                    int(row["qty"]),
                )
            )
        sale_reserved = self._fetch_sale_reserved_bulk(
            sale_products,
            exclude_rental_id=rental_id,
        )
        validation_start = time.perf_counter()
        for product_id, qty in aggregated_items:
            product = product_details.get(product_id)
            if not product:
                continue
            kind = ProductKind(product["kind"])
            total_qty = int(product["total_qty"])
            if kind == ProductKind.SERVICE:
                continue
            if kind == ProductKind.SALE:
                reserved_qty = sale_reserved.get(product_id, 0)
=======
        product_details = self._load_product_details(
            [product_id for product_id, _ in aggregated_items]
        )
        current_date = start
        while current_date < end:
            for product_id, qty in aggregated_items:
                product = product_details.get(product_id)
                if not product:
                    raise ValueError(f"Item {product_id} não encontrado.")
                if product["kind"] in (ProductKind.SERVICE.value, ProductKind.SALE.value):
                    continue
                total_qty = product["total_qty"]
                reserved_qty = self.on_loan(
                    product_id,
                    current_date,
                    exclude_rental_id=rental_id,
                )
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
                available_qty = max(total_qty - reserved_qty, 0)
                if qty > available_qty:
                    product_label = product["name"] or f"ID {product_id}"
                    raise ValueError(
<<<<<<< HEAD
                        "Estoque insuficiente para {product}. Disponível {available}, solicitado {requested}.".format(
                            product=product_label,
=======
                        "Estoque insuficiente para {product} na data {day}. "
                        "Disponível {available}, solicitado {requested}.".format(
                            product=product_label,
                            day=current_date.strftime("%d/%m/%Y"),
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
                            available=available_qty,
                            requested=qty,
                        )
                    )
<<<<<<< HEAD
                continue
            # Rental products consider reserved intervals
            conflicts_for_product = conflicts_by_product.get(product_id, [])
            peak_reserved, blocking_date = self._peak_reserved_capacity(
                conflicts_for_product,
                range_start,
                range_end,
                requested_qty=qty,
                total_qty=total_qty,
            )
            available_qty = max(total_qty - peak_reserved, 0)
            if qty > available_qty:
                product_label = product["name"] or f"ID {product_id}"
                date_label = (
                    blocking_date.strftime("%d/%m/%Y")
                    if blocking_date
                    else range_start.strftime("%d/%m/%Y")
                )
                raise ValueError(
                    "Estoque insuficiente para {product} na data {day}. Disponível {available}, solicitado {requested}.".format(
                        product=product_label,
                        day=date_label,
                        available=available_qty,
                        requested=qty,
                    )
                )
        elapsed = time.perf_counter() - validation_start
        self._logger.info(
            "Validação de estoque concluída para %s itens (conflitos avaliados=%s) em %.3fs",
            len(aggregated_items),
            len(conflicts),
            elapsed,
        )
=======
            current_date += timedelta(days=1)
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d

    def _aggregate_items(
        self, items: Iterable[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        aggregated: dict[int, int] = {}
        for product_id, qty in items:
            aggregated[int(product_id)] = aggregated.get(int(product_id), 0) + int(qty)
        return list(aggregated.items())

    def _load_product_details(self, product_ids: Iterable[int]) -> dict[int, dict]:
        ids = sorted({int(product_id) for product_id in product_ids})
        if not ids:
            return {}
        placeholders = ", ".join(["?"] * len(ids))
        try:
            rows = self._connection.execute(
                f"""
                SELECT id, name, total_qty, kind
                FROM products
                WHERE id IN ({placeholders})
                """,
                ids,
            ).fetchall()
        except Exception:
            self._logger.exception("Failed to load products for availability check")
            raise
        return {
            int(row["id"]): {
                "name": row["name"],
                "total_qty": int(row["total_qty"]),
                "kind": row["kind"] if "kind" in row.keys() else ProductKind.RENTAL.value,
            }
            for row in rows
        }

<<<<<<< HEAD
    def _fetch_conflicting_reservations(
        self,
        product_ids: list[int],
        range_start: date,
        range_end: date,
        *,
        exclude_rental_id: Optional[int],
    ) -> list[dict[str, object]]:
        if not product_ids:
            return []
        placeholders = ", ".join(["?"] * len(product_ids))
        status_placeholders = ", ".join(["?"] * len(RENTAL_BLOCKING_STATUSES))
        params: list[object] = [
            *product_ids,
            *RENTAL_BLOCKING_STATUSES,
            range_end.isoformat(),
            range_start.isoformat(),
        ]
        exclude_clause = ""
        if exclude_rental_id is not None:
            exclude_clause = "AND r.id <> ?"
            params.append(exclude_rental_id)
        query = f"""
            SELECT
                ri.product_id,
                ri.qty,
                COALESCE(r.start_date, r.event_date) AS start_date,
                COALESCE(r.end_date, COALESCE(r.start_date, r.event_date)) AS end_date
            FROM rental_items ri
            JOIN rentals r ON r.id = ri.rental_id
            WHERE ri.product_id IN ({placeholders})
              AND r.status IN ({status_placeholders})
              AND COALESCE(r.start_date, r.event_date) < ?
              AND COALESCE(r.end_date, COALESCE(r.start_date, r.event_date)) > ?
              {exclude_clause}
        """
        try:
            rows = self._connection.execute(query, params).fetchall()
        except Exception:
            self._logger.exception("Falha ao buscar reservas em conflito para itens %s", product_ids)
            raise
        results: list[dict[str, object]] = []
        for row in rows:
            start_value = _ensure_date_obj(row["start_date"])
            end_value = _ensure_date_obj(row["end_date"])
            if start_value is None:
                continue
            if end_value is None or end_value <= start_value:
                end_value = start_value + timedelta(days=1)
            results.append(
                {
                    "product_id": int(row["product_id"]),
                    "qty": int(row["qty"]),
                    "start_date": start_value,
                    "end_date": end_value,
                }
            )
        return results

    def _peak_reserved_capacity(
        self,
        conflicts: list[tuple[date, date, int]],
        range_start: date,
        range_end: date,
        *,
        requested_qty: int,
        total_qty: int,
    ) -> tuple[int, Optional[date]]:
        if not conflicts:
            return 0, None
        events: list[tuple[date, int]] = []
        for start, end, qty in conflicts:
            overlap_start = max(start, range_start)
            overlap_end = min(end, range_end)
            if overlap_start >= overlap_end:
                continue
            events.append((overlap_start, qty))
            events.append((overlap_end, -qty))
        if not events:
            return 0, None
        events.sort(key=lambda item: (item[0], 0 if item[1] < 0 else 1))
        current = 0
        peak = 0
        blocking_date: Optional[date] = None
        for day, delta in events:
            current += delta
            if current > peak:
                peak = current
            if blocking_date is None and current + requested_qty > total_qty:
                blocking_date = day
        return peak, blocking_date

    def _fetch_sale_reserved_bulk(
        self,
        product_ids: list[int],
        exclude_rental_id: Optional[int],
    ) -> dict[int, int]:
        if not product_ids:
            return {}
        placeholders = ", ".join(["?"] * len(product_ids))
        status_placeholders = ", ".join(["?"] * len(SALE_BLOCKING_STATUSES))
        params: list[object] = [*product_ids, *SALE_BLOCKING_STATUSES]
        exclude_clause = ""
        if exclude_rental_id is not None:
            exclude_clause = "AND r.id <> ?"
            params.append(exclude_rental_id)
        query = f"""
            SELECT ri.product_id, COALESCE(SUM(ri.qty), 0) AS reserved_qty
            FROM rental_items ri
            JOIN rentals r ON r.id = ri.rental_id
            WHERE ri.product_id IN ({placeholders})
              AND r.status IN ({status_placeholders})
              {exclude_clause}
            GROUP BY ri.product_id
        """
        try:
            rows = self._connection.execute(query, params).fetchall()
        except Exception:
            self._logger.exception("Falha ao agrupar reservas para itens de venda.")
            raise
        return {int(row["product_id"]): int(row["reserved_qty"] or 0) for row in rows}

    def _fetch_reserved_on_date(
        self,
        product_ids: list[int],
        reference_date: date,
        exclude_rental_id: Optional[int],
    ) -> dict[int, int]:
        if not product_ids:
            return {}
        placeholders = ", ".join(["?"] * len(product_ids))
        status_placeholders = ", ".join(["?"] * len(RENTAL_BLOCKING_STATUSES))
        params: list[object] = [
            *product_ids,
            *RENTAL_BLOCKING_STATUSES,
            reference_date.isoformat(),
            reference_date.isoformat(),
        ]
        exclude_clause = ""
        if exclude_rental_id is not None:
            exclude_clause = "AND r.id <> ?"
            params.append(exclude_rental_id)
        query = f"""
            SELECT ri.product_id, COALESCE(SUM(ri.qty), 0) AS reserved_qty
            FROM rental_items ri
            JOIN rentals r ON r.id = ri.rental_id
            WHERE ri.product_id IN ({placeholders})
              AND r.status IN ({status_placeholders})
              AND COALESCE(r.start_date, r.event_date) <= ?
              AND COALESCE(r.end_date, COALESCE(r.start_date, r.event_date)) > ?
              {exclude_clause}
            GROUP BY ri.product_id
        """
        try:
            rows = self._connection.execute(query, params).fetchall()
        except Exception:
            self._logger.exception("Falha ao buscar reservas por data de referência.")
            raise
        return {int(row["product_id"]): int(row["reserved_qty"] or 0) for row in rows}

=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
    def get_sale_reserved_qty(
        self, product_id: int, exclude_rental_id: Optional[int] = None
    ) -> int:
        status_placeholders = ", ".join(["?"] * len(SALE_BLOCKING_STATUSES))
        params: list[object] = [product_id, ProductKind.SALE.value, *SALE_BLOCKING_STATUSES]
        exclude_clause = ""
        if exclude_rental_id is not None:
            exclude_clause = "AND r.id <> ?"
            params.append(exclude_rental_id)
        try:
            row = self._connection.execute(
                f"""
                SELECT COALESCE(SUM(ri.qty), 0) AS reserved_qty
                FROM rental_items ri
                JOIN rentals r ON r.id = ri.rental_id
                JOIN products p ON p.id = ri.product_id
                WHERE ri.product_id = ?
                  AND p.kind = ?
                  AND r.status IN ({status_placeholders})
                  {exclude_clause}
                """,
                params,
            ).fetchone()
        except Exception:
            self._logger.exception(
                "Failed to fetch sale reserved qty for product_id=%s", product_id
            )
            raise
        return int(row["reserved_qty"]) if row else 0

    def get_sale_available_qty(
        self, product_id: int, exclude_rental_id: Optional[int] = None
    ) -> int:
        try:
            product_row = self._connection.execute(
                "SELECT total_qty, kind FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
        except Exception:
            self._logger.exception("Failed to fetch product for id=%s", product_id)
            raise
        if not product_row:
            raise ValueError(f"Item {product_id} não encontrado.")
        kind = product_row["kind"] if "kind" in product_row.keys() else None
        if kind != ProductKind.SALE.value:
            return self.available(product_id, date.today(), exclude_rental_id=exclude_rental_id)
        total_qty = int(product_row["total_qty"])
        reserved_qty = self.get_sale_reserved_qty(
            product_id, exclude_rental_id=exclude_rental_id
        )
        return max(total_qty - reserved_qty, 0)

<<<<<<< HEAD
    def get_bulk_status_on_date(
        self,
        product_ids: Iterable[int],
        reference_date: str | date,
        *,
        exclude_rental_id: Optional[int] = None,
    ) -> dict[int, dict[str, Optional[int]]]:
        ids = sorted({int(product_id) for product_id in product_ids if product_id})
        if not ids:
            return {}
        reference = _ensure_date_obj(reference_date)
        if reference is None:
            raise ValueError("Data de referência inválida para cálculo de estoque.")
        product_details = self._load_product_details(ids)
        rental_ids = [
            pid for pid, details in product_details.items() if details["kind"] == ProductKind.RENTAL.value
        ]
        sale_ids = [
            pid for pid, details in product_details.items() if details["kind"] == ProductKind.SALE.value
        ]
        rental_reserved = self._fetch_reserved_on_date(
            rental_ids,
            reference,
            exclude_rental_id=exclude_rental_id,
        )
        sale_reserved = self._fetch_sale_reserved_bulk(
            sale_ids,
            exclude_rental_id=exclude_rental_id,
        )
        status: dict[int, dict[str, Optional[int]]] = {}
        for product_id in ids:
            details = product_details.get(product_id)
            if not details:
                continue
            kind = ProductKind(details["kind"])
            total_qty = int(details["total_qty"])
            if kind == ProductKind.SERVICE:
                status[product_id] = {
                    "reserved": None,
                    "available": None,
                }
                continue
            if kind == ProductKind.SALE:
                reserved_qty = sale_reserved.get(product_id, 0)
                available_qty = max(total_qty - reserved_qty, 0)
                status[product_id] = {
                    "reserved": reserved_qty,
                    "available": available_qty,
                }
                continue
            reserved_qty = rental_reserved.get(product_id, 0)
            available_qty = max(total_qty - reserved_qty, 0)
            status[product_id] = {
                "reserved": reserved_qty,
                "available": available_qty,
            }
        return status

=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
    def validate_sale_availability(
        self,
        items: Iterable[tuple[int, int]],
        exclude_rental_id: Optional[int] = None,
    ) -> None:
        aggregated_items = self._aggregate_items(items)
        product_details = self._load_product_details(
            [product_id for product_id, _ in aggregated_items]
        )
        for product_id, qty in aggregated_items:
            available_qty = self.get_sale_available_qty(
                product_id, exclude_rental_id=exclude_rental_id
            )
            if qty > available_qty:
                product_label = (
                    product_details.get(product_id, {}).get("name") or f"ID {product_id}"
                )
                raise ValueError(
                    "Estoque insuficiente para venda do item {product}. "
                    "Disponível {available}, solicitado {requested}.".format(
                        product=product_label,
                        available=available_qty,
                        requested=qty,
                    )
                )
