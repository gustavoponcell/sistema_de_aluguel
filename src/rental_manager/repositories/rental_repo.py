"""Repository helpers for rental persistence."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from rental_manager.db.connection import get_connection, transaction
from rental_manager.domain.models import PaymentStatus, Rental, RentalItem, RentalStatus
from rental_manager.logging_config import get_logger
from rental_manager.paths import get_db_path
from rental_manager.repositories.mappers import rental_from_row, rental_item_from_row


@dataclass(frozen=True)
class FinanceReport:
    total_received: float
    total_to_receive: float
    rentals_count: int


@dataclass(frozen=True)
class RentalFinanceRow:
    id: int
    customer_name: str
    event_date: str
    start_date: Optional[str]
    end_date: Optional[str]
    status: RentalStatus
    payment_status: PaymentStatus
    total_value: float
    paid_value: float


@dataclass(frozen=True)
class MonthlyMetric:
    month: str
    value: float


@dataclass(frozen=True)
class RankedMetric:
    label: str
    value: float


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


ORDER_DATE_EXPR = "COALESCE(r.start_date, r.event_date)"


def _coerce_status(status: str | RentalStatus) -> RentalStatus:
    if isinstance(status, RentalStatus):
        return status
    return RentalStatus(status)


def _coerce_payment_status(status: str | PaymentStatus) -> PaymentStatus:
    if isinstance(status, PaymentStatus):
        return status
    return PaymentStatus(status)


def _payment_status(paid_value: float, total_value: float) -> PaymentStatus:
    if paid_value <= 0:
        return PaymentStatus.UNPAID
    if paid_value < total_value:
        return PaymentStatus.PARTIAL
    return PaymentStatus.PAID


def _build_items(
    items: Iterable[dict[str, object]],
    *,
    timestamp: str,
) -> tuple[list[dict[str, object]], float]:
    normalized: list[dict[str, object]] = []
    total_value = 0.0
    for item in items:
        qty = int(item["qty"])
        unit_price = float(item["unit_price"])
        line_total = qty * unit_price
        normalized.append(
            {
                "product_id": int(item["product_id"]),
                "qty": qty,
                "unit_price": unit_price,
                "line_total": line_total,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        total_value += line_total
    return normalized, total_value


@contextmanager
def _optional_connection(
    connection: Optional[sqlite3.Connection],
) -> Iterable[sqlite3.Connection]:
    if connection is not None:
        connection.row_factory = sqlite3.Row
        yield connection
        return
    new_connection = get_connection(get_db_path())
    try:
        yield new_connection
    finally:
        new_connection.close()


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(
    connection: sqlite3.Connection,
    table: str,
    column: str,
) -> bool:
    try:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return False
    return any(row["name"] == column for row in rows)


def create_rental(
    customer_id: int,
    event_date: str,
    start_date: Optional[str],
    end_date: Optional[str],
    address: Optional[str],
    contact_phone: Optional[str],
    delivery_required: bool,
    items: Iterable[dict[str, object]],
    total_value: Optional[float],
    paid_value: float = 0,
    status: str | RentalStatus = RentalStatus.DRAFT,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> Rental:
    """Create a rental and its items in a transaction."""
    logger = get_logger("rental_repo")
    created_at = _now_iso()
    normalized_items, computed_total = _build_items(items, timestamp=created_at)
    final_total = computed_total if total_value is None else float(total_value)
    payment_status = _payment_status(paid_value, final_total)
    rental_status = _coerce_status(status)
    try:
        with _optional_connection(connection) as conn:
            with transaction(conn):
                cursor = conn.execute(
                    """
                    INSERT INTO rentals (
                        customer_id,
                        event_date,
                        start_date,
                        end_date,
                        address,
                        contact_phone,
                        delivery_required,
                        status,
                        total_value,
                        paid_value,
                        payment_status,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        customer_id,
                        event_date,
                        start_date,
                        end_date,
                        address,
                        contact_phone,
                        int(delivery_required),
                        rental_status.value,
                        final_total,
                        paid_value,
                        payment_status.value,
                        created_at,
                        created_at,
                    ),
                )
                rental_id = cursor.lastrowid
                for item in normalized_items:
                    conn.execute(
                        """
                        INSERT INTO rental_items (
                            rental_id,
                            product_id,
                            qty,
                            unit_price,
                            line_total,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rental_id,
                            item["product_id"],
                            item["qty"],
                            item["unit_price"],
                            item["line_total"],
                            item["created_at"],
                            item["updated_at"],
                        ),
                    )
    except Exception:
        logger.exception("Failed to create rental")
        raise

    return Rental(
        id=rental_id,
        customer_id=customer_id,
        event_date=event_date,
        start_date=start_date,
        end_date=end_date,
        address=address,
        contact_phone=contact_phone,
        delivery_required=delivery_required,
        status=rental_status,
        total_value=final_total,
        paid_value=paid_value,
        payment_status=payment_status,
        created_at=created_at,
        updated_at=created_at,
    )


def update_rental(
    rental_id: int,
    customer_id: int,
    event_date: str,
    start_date: Optional[str],
    end_date: Optional[str],
    address: Optional[str],
    contact_phone: Optional[str],
    delivery_required: bool,
    items: Iterable[dict[str, object]],
    total_value: Optional[float],
    paid_value: float,
    status: str | RentalStatus,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> Optional[Rental]:
    """Update rental data and replace items in a transaction."""
    logger = get_logger("rental_repo")
    updated_at = _now_iso()
    normalized_items, computed_total = _build_items(items, timestamp=updated_at)
    final_total = computed_total if total_value is None else float(total_value)
    payment_status = _payment_status(paid_value, final_total)
    rental_status = _coerce_status(status)
    try:
        with _optional_connection(connection) as conn:
            with transaction(conn):
                cursor = conn.execute(
                    """
                    UPDATE rentals
                    SET
                        customer_id = ?,
                        event_date = ?,
                        start_date = ?,
                        end_date = ?,
                        address = ?,
                        contact_phone = ?,
                        delivery_required = ?,
                        status = ?,
                        total_value = ?,
                        paid_value = ?,
                        payment_status = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        customer_id,
                        event_date,
                        start_date,
                        end_date,
                        address,
                        contact_phone,
                        int(delivery_required),
                        rental_status.value,
                        final_total,
                        paid_value,
                        payment_status.value,
                        updated_at,
                        rental_id,
                    ),
                )
                if cursor.rowcount == 0:
                    return None
                conn.execute(
                    "DELETE FROM rental_items WHERE rental_id = ?",
                    (rental_id,),
                )
                for item in normalized_items:
                    conn.execute(
                        """
                        INSERT INTO rental_items (
                            rental_id,
                            product_id,
                            qty,
                            unit_price,
                            line_total,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rental_id,
                            item["product_id"],
                            item["qty"],
                            item["unit_price"],
                            item["line_total"],
                            item["created_at"],
                            item["updated_at"],
                        ),
                    )
    except Exception:
        logger.exception("Failed to update rental id=%s", rental_id)
        raise

    return Rental(
        id=rental_id,
        customer_id=customer_id,
        event_date=event_date,
        start_date=start_date,
        end_date=end_date,
        address=address,
        contact_phone=contact_phone,
        delivery_required=delivery_required,
        status=rental_status,
        total_value=final_total,
        paid_value=paid_value,
        payment_status=payment_status,
        updated_at=updated_at,
    )


def set_status(
    rental_id: int,
    status: str | RentalStatus,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> bool:
    """Update rental status."""
    logger = get_logger("rental_repo")
    updated_at = _now_iso()
    rental_status = _coerce_status(status)
    try:
        with _optional_connection(connection) as conn:
            with transaction(conn):
                cursor = conn.execute(
                    """
                    UPDATE rentals
                    SET status = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (rental_status.value, updated_at, rental_id),
                )
    except Exception:
        logger.exception("Failed to update rental status id=%s", rental_id)
        raise
    return cursor.rowcount > 0


def set_payment(
    rental_id: int,
    paid_value: float,
    payment_status: str | PaymentStatus,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> bool:
    """Update rental payment fields."""
    logger = get_logger("rental_repo")
    updated_at = _now_iso()
    status_value = _coerce_payment_status(payment_status)
    try:
        with _optional_connection(connection) as conn:
            with transaction(conn):
                cursor = conn.execute(
                    """
                    UPDATE rentals
                    SET paid_value = ?,
                        payment_status = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (paid_value, status_value.value, updated_at, rental_id),
                )
    except Exception:
        logger.exception("Failed to update rental payment id=%s", rental_id)
        raise
    return cursor.rowcount > 0


def get_finance_report_by_period(
    start_date: str,
    end_date: str,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> FinanceReport:
    """Return aggregate finance totals for the given start date period."""
    logger = get_logger("rental_repo")
    try:
        with _optional_connection(connection) as conn:
            if _table_exists(conn, "payments"):
                received_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) AS total_received
                    FROM payments
                    WHERE paid_at IS NOT NULL
                      AND date(paid_at) >= ?
                      AND date(paid_at) <= ?
                    """,
                    (start_date, end_date),
                ).fetchone()
            else:
                received_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(paid_value), 0) AS total_received
                    FROM rentals
                    WHERE COALESCE(start_date, event_date) >= ?
                      AND COALESCE(start_date, event_date) <= ?
                      AND status != 'canceled'
                    """,
                    (start_date, end_date),
                ).fetchone()
            totals_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN r.status = 'confirmed'
                            THEN CASE
                                WHEN (r.total_value - r.paid_value) > 0
                                THEN (r.total_value - r.paid_value)
                                ELSE 0
                            END
                            ELSE 0
                        END
                    ), 0) AS total_to_receive,
                    COUNT(*) AS rentals_count
                FROM rentals r
                WHERE COALESCE(r.start_date, r.event_date) >= ?
                  AND COALESCE(r.start_date, r.event_date) <= ?
                  AND r.status != 'canceled'
                """,
                (start_date, end_date),
            ).fetchone()
    except Exception:
        logger.exception("Failed to build finance report")
        raise
    if not totals_row:
        return FinanceReport(total_received=0.0, total_to_receive=0.0, rentals_count=0)
    return FinanceReport(
        total_received=float(received_row["total_received"] or 0)
        if received_row
        else 0.0,
        total_to_receive=float(totals_row["total_to_receive"] or 0),
        rentals_count=int(totals_row["rentals_count"] or 0),
    )


def list_rentals_by_period(
    start_date: str,
    end_date: str,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> list[RentalFinanceRow]:
    """List rentals for finance reports in the given start date period."""
    logger = get_logger("rental_repo")
    query = f"""
        SELECT
            r.id,
            r.event_date,
            r.start_date,
            r.end_date,
            r.status,
            r.total_value,
            r.paid_value,
            r.payment_status,
            c.name AS customer_name
        FROM rentals r
        JOIN customers c ON c.id = r.customer_id
        WHERE {ORDER_DATE_EXPR} >= ?
          AND {ORDER_DATE_EXPR} <= ?
          AND r.status != 'canceled'
        ORDER BY {ORDER_DATE_EXPR}, r.event_date, r.id
    """
    try:
        with _optional_connection(connection) as conn:
            rows = conn.execute(query, (start_date, end_date)).fetchall()
    except Exception:
        logger.exception("Failed to list rentals by period")
        raise
    result: list[RentalFinanceRow] = []
    for row in rows:
        result.append(
            RentalFinanceRow(
                id=int(row["id"]),
                customer_name=row["customer_name"],
                event_date=row["event_date"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                status=RentalStatus(row["status"]),
                payment_status=PaymentStatus(row["payment_status"]),
                total_value=float(row["total_value"]),
                paid_value=float(row["paid_value"]),
            )
        )
    return result


def list_monthly_revenue(
    start_date: str,
    end_date: str,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> list[MonthlyMetric]:
    """Sum rental total_value by month using rentals.start_date."""
    logger = get_logger("rental_repo")
    query = f"""
        SELECT
            strftime('%Y-%m', {ORDER_DATE_EXPR}) AS month,
            COALESCE(SUM(r.total_value), 0) AS total_value
        FROM rentals r
        WHERE {ORDER_DATE_EXPR} >= ?
          AND {ORDER_DATE_EXPR} <= ?
          AND r.status != 'canceled'
        GROUP BY strftime('%Y-%m', {ORDER_DATE_EXPR})
        ORDER BY month
    """
    try:
        with _optional_connection(connection) as conn:
            rows = conn.execute(query, (start_date, end_date)).fetchall()
    except Exception:
        logger.exception("Failed to list monthly revenue")
        raise
    return [
        MonthlyMetric(month=row["month"], value=float(row["total_value"] or 0))
        for row in rows
        if row["month"]
    ]


def list_monthly_rentals(
    start_date: str,
    end_date: str,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> list[MonthlyMetric]:
    """Count rentals by month using rentals.start_date."""
    logger = get_logger("rental_repo")
    query = f"""
        SELECT
            strftime('%Y-%m', {ORDER_DATE_EXPR}) AS month,
            COUNT(*) AS total_count
        FROM rentals r
        WHERE {ORDER_DATE_EXPR} >= ?
          AND {ORDER_DATE_EXPR} <= ?
          AND r.status != 'canceled'
        GROUP BY strftime('%Y-%m', {ORDER_DATE_EXPR})
        ORDER BY month
    """
    try:
        with _optional_connection(connection) as conn:
            rows = conn.execute(query, (start_date, end_date)).fetchall()
    except Exception:
        logger.exception("Failed to list monthly rentals")
        raise
    return [
        MonthlyMetric(month=row["month"], value=float(row["total_count"] or 0))
        for row in rows
        if row["month"]
    ]


def list_monthly_received(
    start_date: str,
    end_date: str,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> list[MonthlyMetric]:
    """Sum received amounts by month using payments.paid_at or rentals.start_date."""
    logger = get_logger("rental_repo")
    try:
        with _optional_connection(connection) as conn:
            if _table_exists(conn, "payments"):
                query = """
                    SELECT
                        strftime('%Y-%m', paid_at) AS month,
                        COALESCE(SUM(amount), 0) AS total_received
                    FROM payments
                    WHERE paid_at IS NOT NULL
                      AND date(paid_at) >= ?
                      AND date(paid_at) <= ?
                    GROUP BY strftime('%Y-%m', paid_at)
                    ORDER BY month
                """
                rows = conn.execute(query, (start_date, end_date)).fetchall()
            else:
                query = f"""
                    SELECT
                        strftime('%Y-%m', {ORDER_DATE_EXPR}) AS month,
                        COALESCE(SUM(r.paid_value), 0) AS total_received
                    FROM rentals r
                    WHERE {ORDER_DATE_EXPR} >= ?
                      AND {ORDER_DATE_EXPR} <= ?
                      AND r.status != 'canceled'
                    GROUP BY strftime('%Y-%m', {ORDER_DATE_EXPR})
                    ORDER BY month
                """
                rows = conn.execute(query, (start_date, end_date)).fetchall()
    except Exception:
        logger.exception("Failed to list monthly received values")
        raise
    return [
        MonthlyMetric(month=row["month"], value=float(row["total_received"] or 0))
        for row in rows
        if row["month"]
    ]


def list_monthly_to_receive(
    start_date: str,
    end_date: str,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> list[MonthlyMetric]:
    """Sum open receivables by month using rentals.start_date."""
    logger = get_logger("rental_repo")
    query = f"""
        SELECT
            strftime('%Y-%m', {ORDER_DATE_EXPR}) AS month,
            COALESCE(SUM(
                CASE
                    WHEN r.status = 'confirmed'
                    THEN CASE
                        WHEN (r.total_value - r.paid_value) > 0
                        THEN (r.total_value - r.paid_value)
                        ELSE 0
                    END
                    ELSE 0
                END
            ), 0) AS total_open
        FROM rentals r
        WHERE {ORDER_DATE_EXPR} >= ?
          AND {ORDER_DATE_EXPR} <= ?
          AND r.status != 'canceled'
        GROUP BY strftime('%Y-%m', {ORDER_DATE_EXPR})
        ORDER BY month
    """
    try:
        with _optional_connection(connection) as conn:
            rows = conn.execute(query, (start_date, end_date)).fetchall()
    except Exception:
        logger.exception("Failed to list monthly receivables")
        raise
    return [
        MonthlyMetric(month=row["month"], value=float(row["total_open"] or 0))
        for row in rows
        if row["month"]
    ]


def list_top_products_by_qty(
    start_date: str,
    end_date: str,
    *,
    limit: int = 10,
    connection: Optional[sqlite3.Connection] = None,
) -> list[RankedMetric]:
    """Return top products by rented quantity for the given start date period."""
    logger = get_logger("rental_repo")
    query = f"""
        SELECT
            COALESCE(p.name, 'Produto removido') AS product_name,
            COALESCE(SUM(ri.qty), 0) AS total_qty
        FROM rental_items ri
        JOIN rentals r ON r.id = ri.rental_id
        LEFT JOIN products p ON p.id = ri.product_id
        WHERE {ORDER_DATE_EXPR} >= ?
          AND {ORDER_DATE_EXPR} <= ?
          AND r.status != 'canceled'
        GROUP BY ri.product_id, p.name
        ORDER BY total_qty DESC
        LIMIT ?
    """
    try:
        with _optional_connection(connection) as conn:
            rows = conn.execute(query, (start_date, end_date, limit)).fetchall()
    except Exception:
        logger.exception("Failed to list top products by quantity")
        raise
    return [
        RankedMetric(label=row["product_name"], value=float(row["total_qty"] or 0))
        for row in rows
    ]


def list_top_products_by_revenue(
    start_date: str,
    end_date: str,
    *,
    limit: int = 10,
    connection: Optional[sqlite3.Connection] = None,
) -> Optional[list[RankedMetric]]:
    """Return top products by revenue, if price columns are available."""
    logger = get_logger("rental_repo")
    try:
        with _optional_connection(connection) as conn:
            has_item_price = _column_exists(conn, "rental_items", "unit_price")
            has_product_price = _column_exists(conn, "products", "unit_price")
            if not has_item_price and not has_product_price:
                return None
            if has_item_price:
                price_expr = "ri.qty * ri.unit_price"
                join_products = "LEFT JOIN products p ON p.id = ri.product_id"
            else:
                price_expr = "ri.qty * p.unit_price"
                join_products = "JOIN products p ON p.id = ri.product_id"
            query = f"""
                SELECT
                    COALESCE(p.name, 'Produto removido') AS product_name,
                    COALESCE(SUM({price_expr}), 0) AS total_revenue
                FROM rental_items ri
                JOIN rentals r ON r.id = ri.rental_id
                {join_products}
                WHERE {ORDER_DATE_EXPR} >= ?
                  AND {ORDER_DATE_EXPR} <= ?
                  AND r.status != 'canceled'
                GROUP BY ri.product_id, p.name
                ORDER BY total_revenue DESC
                LIMIT ?
            """
            rows = conn.execute(query, (start_date, end_date, limit)).fetchall()
    except Exception:
        logger.exception("Failed to list top products by revenue")
        raise
    return [
        RankedMetric(label=row["product_name"], value=float(row["total_revenue"] or 0))
        for row in rows
    ]


def list_rentals(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str | RentalStatus] = None,
    payment_status: Optional[str | PaymentStatus] = None,
    search: Optional[str] = None,
    connection: Optional[sqlite3.Connection] = None,
) -> list[Rental]:
    """List rentals with optional filters (event date, status, payment, search)."""
    logger = get_logger("rental_repo")
    clauses: list[str] = []
    params: list[object] = []
    if start_date:
        clauses.append("r.event_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("r.event_date <= ?")
        params.append(end_date)
    if status:
        clauses.append("r.status = ?")
        params.append(_coerce_status(status).value)
    if payment_status:
        status_value = (
            payment_status.value
            if isinstance(payment_status, PaymentStatus)
            else str(payment_status)
        )
        clauses.append("r.payment_status = ?")
        params.append(status_value)
    if search:
        clauses.append("(r.address LIKE ? OR c.name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT r.*
        FROM rentals r
        JOIN customers c ON c.id = r.customer_id
        {where_clause}
        ORDER BY r.event_date, r.start_date, r.id
    """
    try:
        with _optional_connection(connection) as conn:
            rows = conn.execute(query, params).fetchall()
    except Exception:
        logger.exception("Failed to list rentals")
        raise
    return [rental_from_row(row) for row in rows]


def get_rental_with_items(
    rental_id: int,
    *,
    connection: Optional[sqlite3.Connection] = None,
) -> Optional[tuple[Rental, list[RentalItem]]]:
    """Fetch a rental and its items."""
    logger = get_logger("rental_repo")
    try:
        with _optional_connection(connection) as conn:
            rental_row = conn.execute(
                "SELECT * FROM rentals WHERE id = ?",
                (rental_id,),
            ).fetchone()
            if not rental_row:
                return None
            item_rows = conn.execute(
                """
                SELECT * FROM rental_items
                WHERE rental_id = ?
                ORDER BY id
                """,
                (rental_id,),
            ).fetchall()
    except Exception:
        logger.exception("Failed to fetch rental id=%s", rental_id)
        raise
    return rental_from_row(rental_row), [
        rental_item_from_row(row) for row in item_rows
    ]
