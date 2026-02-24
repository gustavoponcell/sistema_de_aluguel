"""Seed demo data into the RentalManager SQLite database."""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rental_manager.db.connection import get_connection
from rental_manager.db.schema import init_db
from rental_manager.domain.models import (
    Customer,
    Document,
    DocumentType,
    PaymentStatus,
    ProductKind,
    Rental,
    RentalStatus,
)
from rental_manager.paths import get_config_path, get_db_path, get_pdfs_dir
from rental_manager.services.inventory_service import InventoryService
from rental_manager.utils.documents import build_document_filename, load_documents_settings
from rental_manager.utils.pdf_generator import generate_rental_pdf

SEED_TAG = "Seed Demo"
DEFAULT_SEED = 42


@dataclass(frozen=True)
class ProductSeed:
    key: str
    name: str
    category: str
    total_qty: int
    unit_price: float
    kind: ProductKind


@dataclass
class PaymentSeed:
    amount: float
    method: str
    paid_at: datetime


@dataclass
class SeedOrder:
    rental_id: int
    rental: Rental
    customer: Customer
    items: list[SimpleNamespace]
    status: RentalStatus
    payment_status: PaymentStatus


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo data for RentalManager")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove o banco atual e recria antes de inserir dados.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Seed para aleatoriedade.",
    )
    return parser.parse_args()


def _get_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
    return {row["name"] for row in rows}


def _get_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table});").fetchall()
    return {row["name"] for row in rows}


def _insert_row(
    connection: sqlite3.Connection,
    table: str,
    data: dict,
    columns: set[str],
) -> int:
    filtered = {key: value for key, value in data.items() if key in columns}
    if not filtered:
        raise ValueError(f"Nenhuma coluna válida para inserir em {table}.")
    placeholders = ", ".join(["?"] * len(filtered))
    column_list = ", ".join(filtered.keys())
    cursor = connection.execute(
        f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
        tuple(filtered.values()),
    )
    return int(cursor.lastrowid)


def _maybe_insert_product(
    connection: sqlite3.Connection,
    product: ProductSeed,
    columns: set[str],
    now: str,
) -> int:
    existing = connection.execute(
        "SELECT id FROM products WHERE name = ?",
        (product.name,),
    ).fetchone()
    if existing:
        return int(existing["id"])
    data = {
        "name": product.name,
        "category": product.category,
        "total_qty": product.total_qty,
        "unit_price": product.unit_price,
        "kind": product.kind.value,
        "active": 1,
        "created_at": now,
        "updated_at": now,
    }
    return _insert_row(connection, "products", data, columns)


def _load_seed_products() -> list[ProductSeed]:
    return [
        ProductSeed(
            key="chairs",
            name=f"{SEED_TAG} - Cadeiras",
            category="cadeira",
            total_qty=200,
            unit_price=2.5,
            kind=ProductKind.RENTAL,
        ),
        ProductSeed(
            key="tables",
            name=f"{SEED_TAG} - Mesas",
            category="mesa",
            total_qty=40,
            unit_price=8.0,
            kind=ProductKind.RENTAL,
        ),
        ProductSeed(
            key="jump",
            name=f"{SEED_TAG} - Pula-pula",
            category="brinquedo",
            total_qty=2,
            unit_price=350.0,
            kind=ProductKind.RENTAL,
        ),
        ProductSeed(
            key="ball_pool",
            name=f"{SEED_TAG} - Piscina de bolinhas",
            category="brinquedo",
            total_qty=1,
            unit_price=280.0,
            kind=ProductKind.RENTAL,
        ),
        ProductSeed(
            key="sound",
            name=f"{SEED_TAG} - Caixa de som",
            category="som",
            total_qty=3,
            unit_price=120.0,
            kind=ProductKind.RENTAL,
        ),
        ProductSeed(
            key="lighting",
            name=f"{SEED_TAG} - Iluminação",
            category="luz",
            total_qty=2,
            unit_price=150.0,
            kind=ProductKind.RENTAL,
        ),
        ProductSeed(
            key="tablecloth",
            name=f"{SEED_TAG} - Toalhas de mesa",
            category="decoracao",
            total_qty=60,
            unit_price=3.0,
            kind=ProductKind.RENTAL,
        ),
        ProductSeed(
            key="disposable",
            name=f"{SEED_TAG} - Kit descartáveis",
            category="venda",
            total_qty=120,
            unit_price=12.0,
            kind=ProductKind.SALE,
        ),
        ProductSeed(
            key="balloons",
            name=f"{SEED_TAG} - Balões decorativos",
            category="venda",
            total_qty=200,
            unit_price=1.8,
            kind=ProductKind.SALE,
        ),
        ProductSeed(
            key="candles",
            name=f"{SEED_TAG} - Velas de aniversário",
            category="venda",
            total_qty=80,
            unit_price=4.0,
            kind=ProductKind.SALE,
        ),
        ProductSeed(
            key="face_painting",
            name=f"{SEED_TAG} - Pintura facial",
            category="servico",
            total_qty=999,
            unit_price=150.0,
            kind=ProductKind.SERVICE,
        ),
        ProductSeed(
            key="animator",
            name=f"{SEED_TAG} - Animadores de festa",
            category="servico",
            total_qty=999,
            unit_price=300.0,
            kind=ProductKind.SERVICE,
        ),
        ProductSeed(
            key="popcorn",
            name=f"{SEED_TAG} - Carrinho de pipoca",
            category="servico",
            total_qty=999,
            unit_price=250.0,
            kind=ProductKind.SERVICE,
        ),
        ProductSeed(
            key="cotton_candy",
            name=f"{SEED_TAG} - Carrinho de algodão doce",
            category="servico",
            total_qty=999,
            unit_price=230.0,
            kind=ProductKind.SERVICE,
        ),
    ]


def _random_phone(rng: random.Random) -> str:
    prefix = rng.choice(["11", "21", "31", "41", "51", "61", "71", "81", "91"])
    return f"({prefix}) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"


def _build_customers(rng: random.Random, count: int) -> list[dict]:
    first_names = [
        "Ana",
        "Beatriz",
        "Carla",
        "Daniela",
        "Eduardo",
        "Fernanda",
        "Gabriel",
        "Helena",
        "Igor",
        "Juliana",
        "Marcos",
        "Natália",
        "Paulo",
        "Rafael",
        "Sofia",
        "Thiago",
        "Vitor",
        "Yasmin",
    ]
    last_names = [
        "Silva",
        "Souza",
        "Almeida",
        "Ferreira",
        "Gomes",
        "Ribeiro",
        "Carvalho",
        "Lima",
        "Pereira",
        "Costa",
        "Rodrigues",
        "Oliveira",
    ]

    customers = []
    for index in range(1, count + 1):
        first = rng.choice(first_names)
        last = rng.choice(last_names)
        name = f"{SEED_TAG} Cliente {index:02d} - {first} {last}"
        customers.append(
            {
                "name": name,
                "phone": _random_phone(rng),
                "notes": f"{SEED_TAG} gerado automaticamente.",
            }
        )
    return customers


def _random_address(rng: random.Random) -> str:
    streets = [
        "Rua das Flores",
        "Avenida Paulista",
        "Rua do Sol",
        "Rua das Palmeiras",
        "Rua da Alegria",
        "Avenida Brasil",
        "Rua dos Lírios",
        "Rua do Comércio",
    ]
    neighborhoods = [
        "Centro",
        "Jardim Primavera",
        "Vila Nova",
        "Bela Vista",
        "Parque das Flores",
        "Alto do Lago",
        "Santa Clara",
        "Jardim das Acácias",
    ]
    cities = ["São Paulo", "Campinas", "Guarulhos", "Osasco", "Santo André"]
    number = rng.randint(20, 999)
    street = rng.choice(streets)
    bairro = rng.choice(neighborhoods)
    cidade = rng.choice(cities)
    return f"{SEED_TAG} - {street}, {number} - {bairro}, {cidade}"


def _date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current < end:
        yield current
        current += timedelta(days=1)


def _pick_start_date(rng: random.Random, candidates: list[date]) -> date:
    weights = []
    for day in candidates:
        if day.weekday() >= 4:
            weights.append(4)
        elif day.weekday() == 3:
            weights.append(2)
        else:
            weights.append(1)
    return rng.choices(candidates, weights=weights, k=1)[0]


def _pick_duration(rng: random.Random) -> int:
    return rng.choices([1, 2, 3, 4], weights=[50, 35, 10, 5], k=1)[0]


def _min_available_for_range(
    inventory: InventoryService,
    product_id: int,
    total_qty: int,
    start: date,
    end: date,
) -> int:
    available = total_qty
    for day in _date_range(start, end):
        reserved = inventory.on_loan(product_id, day)
        available = min(available, max(total_qty - reserved, 0))
        if available <= 0:
            return 0
    return available


def _adjust_items_for_availability(
    inventory: InventoryService,
    items: list[dict],
    product_totals: dict[int, int],
    start: date,
    end: date,
) -> list[dict]:
    adjusted: list[dict] = []
    for item in items:
        product_id = item["product_id"]
        desired_qty = item["qty"]
        total_qty = product_totals.get(product_id, 0)
        if total_qty <= 0:
            continue
        max_available = _min_available_for_range(
            inventory, product_id, total_qty, start, end
        )
        if max_available <= 0:
            continue
        if desired_qty > max_available:
            item = dict(item)
            item["qty"] = max_available
            item["line_total"] = max_available * item["unit_price"]
        adjusted.append(item)
    return adjusted


def _adjust_sale_items(
    inventory: InventoryService,
    items: list[dict],
) -> list[dict]:
    adjusted: list[dict] = []
    for item in items:
        product_id = item["product_id"]
        desired_qty = item["qty"]
        available = inventory.get_sale_available_qty(product_id)
        if available <= 0:
            continue
        if desired_qty > available:
            item = dict(item)
            item["qty"] = available
            item["line_total"] = available * item["unit_price"]
        adjusted.append(item)
    return adjusted


def _build_rental_items(
    rng: random.Random,
    product_map: dict[str, dict],
) -> list[dict]:
    items: list[dict] = []

    def add_item(key: str, qty: int) -> None:
        product = product_map[key]
        items.append(
            {
                "product_id": product["id"],
                "qty": qty,
                "unit_price": product["unit_price"],
                "line_total": qty * product["unit_price"],
                "kind": product["kind"],
            }
        )

    add_item("chairs", rng.randint(30, 180))
    add_item("tables", rng.randint(5, 30))

    if rng.random() < 0.35:
        add_item("jump", 1)
    if rng.random() < 0.25:
        add_item("ball_pool", 1)
    if rng.random() < 0.4:
        add_item("sound", rng.randint(1, 2))
    if rng.random() < 0.3:
        add_item("lighting", rng.randint(1, 2))
    if rng.random() < 0.5:
        add_item("tablecloth", rng.randint(10, 60))

    return items


def _build_service_items(rng: random.Random, product_map: dict[str, dict]) -> list[dict]:
    items: list[dict] = []
    service_keys = ["face_painting", "animator", "popcorn", "cotton_candy"]
    rng.shuffle(service_keys)
    for service_key in service_keys[: rng.randint(1, 2)]:
        product = product_map[service_key]
        items.append(
            {
                "product_id": product["id"],
                "qty": 1,
                "unit_price": product["unit_price"],
                "line_total": product["unit_price"],
                "kind": product["kind"],
            }
        )
    return items


def _build_sale_items(rng: random.Random, product_map: dict[str, dict]) -> list[dict]:
    items: list[dict] = []
    sale_keys = ["disposable", "balloons", "candles"]
    rng.shuffle(sale_keys)
    for key in sale_keys[: rng.randint(1, 3)]:
        product = product_map[key]
        qty = rng.randint(1, 12)
        items.append(
            {
                "product_id": product["id"],
                "qty": qty,
                "unit_price": product["unit_price"],
                "line_total": qty * product["unit_price"],
                "kind": product["kind"],
            }
        )
    return items


def _pick_status(rng: random.Random, order_type: str) -> RentalStatus:
    if order_type == "sale":
        choices = [
            RentalStatus.DRAFT,
            RentalStatus.CONFIRMED,
            RentalStatus.COMPLETED,
            RentalStatus.CANCELED,
        ]
        weights = [10, 35, 45, 10]
    elif order_type == "service":
        choices = [
            RentalStatus.DRAFT,
            RentalStatus.CONFIRMED,
            RentalStatus.COMPLETED,
            RentalStatus.CANCELED,
        ]
        weights = [15, 40, 35, 10]
    else:
        choices = [
            RentalStatus.DRAFT,
            RentalStatus.CONFIRMED,
            RentalStatus.COMPLETED,
            RentalStatus.CANCELED,
        ]
        weights = [20, 45, 25, 10]
    return rng.choices(choices, weights=weights, k=1)[0]


def _build_payments(
    rng: random.Random,
    status: RentalStatus,
    total_value: float,
    reference_date: date,
) -> tuple[float, list[PaymentSeed]]:
    if status == RentalStatus.CANCELED or total_value <= 0:
        return 0.0, []

    if status == RentalStatus.DRAFT:
        paid_total = rng.choice([0.0, round(total_value * 0.2, 2)])
    else:
        if rng.random() < 0.55:
            paid_total = total_value
        else:
            paid_total = round(total_value * rng.uniform(0.4, 0.8), 2)

    paid_total = min(paid_total, total_value)
    if paid_total <= 0:
        return 0.0, []

    payment_count = rng.randint(1, 3)
    amounts = []
    remaining = paid_total
    for index in range(payment_count):
        if index == payment_count - 1:
            amounts.append(round(remaining, 2))
        else:
            portion = round(rng.uniform(0.2, 0.6) * remaining, 2)
            portion = min(portion, remaining)
            amounts.append(portion)
            remaining = round(remaining - portion, 2)

    methods = ["PIX", "Dinheiro", "Cartão"]
    payments: list[PaymentSeed] = []
    for amount in amounts:
        paid_at = datetime.combine(
            reference_date - timedelta(days=rng.randint(0, 5)),
            datetime.min.time(),
        ) + timedelta(hours=rng.randint(9, 20))
        payments.append(
            PaymentSeed(
                amount=amount,
                method=rng.choice(methods),
                paid_at=paid_at,
            )
        )
    return paid_total, payments


def _payment_status(paid_value: float, total_value: float) -> PaymentStatus:
    if paid_value <= 0:
        return PaymentStatus.UNPAID
    if paid_value + 0.01 < total_value:
        return PaymentStatus.PARTIAL
    return PaymentStatus.PAID


def _load_documents_dir() -> Path:
    config_path = get_config_path()
    settings = load_documents_settings(config_path)
    if settings.documents_dir:
        return Path(settings.documents_dir)
    return get_pdfs_dir()


def _seed_exists(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT COUNT(*) AS total FROM products WHERE name LIKE ?",
        (f"{SEED_TAG}%",),
    ).fetchone()
    return bool(row and row["total"])


def main() -> None:
    args = _parse_args()
    rng = random.Random(args.seed)

    db_path = get_db_path()
    if args.reset and db_path.exists():
        db_path.unlink()
        print(f"Banco removido: {db_path}")

    print(f"Usando banco de dados: {db_path}")
    init_db(db_path)

    connection = get_connection(db_path)
    connection.row_factory = sqlite3.Row
    try:
        tables = _get_tables(connection)
        if "products" not in tables or "rentals" not in tables:
            raise RuntimeError("Schema inválido: tabelas principais ausentes.")

        if _seed_exists(connection) and not args.reset:
            print(
                "Dados de seed já encontrados. Use --reset para recriar o banco."
            )
            return

        product_columns = _get_columns(connection, "products")
        customer_columns = _get_columns(connection, "customers")
        rental_columns = _get_columns(connection, "rentals")
        rental_item_columns = _get_columns(connection, "rental_items")
        payments_exists = "payments" in tables
        payments_columns = _get_columns(connection, "payments") if payments_exists else set()
        documents_exists = "documents" in tables
        documents_columns = (
            _get_columns(connection, "documents") if documents_exists else set()
        )
        expenses_exists = "expenses" in tables
        expenses_columns = (
            _get_columns(connection, "expenses") if expenses_exists else set()
        )

        now = datetime.now().isoformat(timespec="seconds")
        today = date.today()
        start_window = today - timedelta(days=60)
        date_candidates = [
            start_window + timedelta(days=offset)
            for offset in range((today - start_window).days + 1)
        ]

        seed_products = _load_seed_products()
        product_map: dict[str, dict] = {}

        rental_target = rng.randint(120, 180)
        max_attempts = rental_target * 6

        rental_count = 0
        rental_item_count = 0
        payment_count = 0
        document_count = 0
        total_revenue = 0.0

        seed_orders: list[SeedOrder] = []

        try:
            connection.execute("BEGIN")

            for product in seed_products:
                product_id = _maybe_insert_product(
                    connection, product, product_columns, now
                )
                product_map[product.key] = {
                    "id": product_id,
                    "unit_price": product.unit_price,
                    "kind": product.kind,
                    "total_qty": product.total_qty,
                    "name": product.name,
                }

            customer_ids: list[int] = []
            customer_map: dict[int, Customer] = {}
            customer_count = rng.randint(30, 60)
            for customer in _build_customers(rng, customer_count):
                data = {
                    "name": customer["name"],
                    "phone": customer["phone"],
                    "notes": customer["notes"],
                    "created_at": now,
                    "updated_at": now,
                }
                customer_id = _insert_row(
                    connection, "customers", data, customer_columns
                )
                customer_ids.append(customer_id)
                customer_map[customer_id] = Customer(
                    id=customer_id,
                    name=customer["name"],
                    phone=customer["phone"],
                    notes=customer["notes"],
                    created_at=now,
                    updated_at=now,
                )

            inventory = InventoryService(connection)
            product_totals = {
                info["id"]: info["total_qty"] for info in product_map.values()
            }

            attempts = 0
            while rental_count < rental_target and attempts < max_attempts:
                attempts += 1
                order_type = rng.choices(
                    ["rental", "sale", "service"], weights=[60, 20, 20], k=1
                )[0]
                event_date = _pick_start_date(rng, date_candidates)
                status = _pick_status(rng, order_type)
                customer_id = rng.choice(customer_ids)
                customer = customer_map[customer_id]

                delivery_required = rng.random() < 0.55
                address = _random_address(rng) if delivery_required else None
                contact_phone = customer.phone

                start_date: Optional[date] = None
                end_date: Optional[date] = None
                items: list[dict] = []

                if order_type == "rental":
                    start_date = event_date
                    end_date = event_date + timedelta(days=_pick_duration(rng))
                    items = _build_rental_items(rng, product_map)
                    items = _adjust_items_for_availability(
                        inventory, items, product_totals, start_date, end_date
                    )
                    if not items:
                        continue
                    if rng.random() < 0.6:
                        items.extend(_build_service_items(rng, product_map))
                elif order_type == "sale":
                    items = _build_sale_items(rng, product_map)
                    items = _adjust_sale_items(inventory, items)
                    if not items:
                        continue
                    if rng.random() < 0.3:
                        items.extend(_build_service_items(rng, product_map))
                else:
                    items = _build_service_items(rng, product_map)

                total_value = round(sum(item["line_total"] for item in items), 2)
                paid_value, payment_seeds = _build_payments(
                    rng, status, total_value, event_date
                )
                payment_status = _payment_status(paid_value, total_value)

                rental_data = {
                    "customer_id": customer_id,
                    "event_date": event_date.isoformat(),
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "address": address,
                    "contact_phone": contact_phone,
                    "delivery_required": 1 if delivery_required else 0,
                    "status": status.value,
                    "total_value": total_value,
                    "paid_value": paid_value,
                    "payment_status": payment_status.value,
                    "created_at": now,
                    "updated_at": now,
                }
                rental_id = _insert_row(
                    connection, "rentals", rental_data, rental_columns
                )
                rental_count += 1

                for item in items:
                    item_data = {
                        "rental_id": rental_id,
                        "product_id": item["product_id"],
                        "qty": item["qty"],
                        "unit_price": item["unit_price"],
                        "line_total": item["line_total"],
                        "created_at": now,
                        "updated_at": now,
                    }
                    _insert_row(
                        connection,
                        "rental_items",
                        item_data,
                        rental_item_columns,
                    )
                    rental_item_count += 1

                if payments_exists:
                    for payment in payment_seeds:
                        payment_data = {
                            "rental_id": rental_id,
                            "amount": payment.amount,
                            "method": payment.method,
                            "paid_at": payment.paid_at.isoformat(timespec="seconds"),
                            "note": f"{SEED_TAG} auto",
                        }
                        _insert_row(
                            connection, "payments", payment_data, payments_columns
                        )
                        payment_count += 1

                if status == RentalStatus.COMPLETED:
                    sale_items = [
                        item
                        for item in items
                        if item["kind"] == ProductKind.SALE
                    ]
                    for sale_item in sale_items:
                        connection.execute(
                            """
                            UPDATE products
                            SET total_qty = MAX(total_qty - ?, 0)
                            WHERE id = ?
                            """,
                            (sale_item["qty"], sale_item["product_id"]),
                        )

                rental_record = Rental(
                    id=rental_id,
                    customer_id=customer_id,
                    event_date=event_date.isoformat(),
                    start_date=start_date.isoformat() if start_date else None,
                    end_date=end_date.isoformat() if end_date else None,
                    address=address,
                    status=status,
                    total_value=total_value,
                    paid_value=paid_value,
                    payment_status=payment_status,
                    contact_phone=contact_phone,
                    delivery_required=delivery_required,
                    created_at=now,
                    updated_at=now,
                )
                pdf_items = [
                    SimpleNamespace(
                        product_id=item["product_id"],
                        qty=item["qty"],
                        unit_price=item["unit_price"],
                        line_total=item["line_total"],
                        product_name=next(
                            (
                                info["name"]
                                for info in product_map.values()
                                if info["id"] == item["product_id"]
                            ),
                            f"Produto {item['product_id']}",
                        ),
                    )
                    for item in items
                ]
                seed_orders.append(
                    SeedOrder(
                        rental_id=rental_id,
                        rental=rental_record,
                        customer=customer,
                        items=pdf_items,
                        status=status,
                        payment_status=payment_status,
                    )
                )
                total_revenue += total_value

            if expenses_exists:
                expense_categories = [
                    "Combustível",
                    "Manutenção",
                    "Compra de insumos",
                    "Transporte",
                ]
                for _ in range(rng.randint(10, 18)):
                    exp_date = rng.choice(date_candidates)
                    expense_data = {
                        "created_at": now,
                        "date": exp_date.isoformat(),
                        "category": rng.choice(expense_categories),
                        "description": f"{SEED_TAG} despesa de operação",
                        "amount": round(rng.uniform(40.0, 450.0), 2),
                        "payment_method": rng.choice(["Dinheiro", "PIX", "Cartão"]),
                        "supplier": rng.choice(
                            ["Fornecedor A", "Fornecedor B", "Parceiro Local"]
                        ),
                        "notes": None,
                    }
                    _insert_row(
                        connection, "expenses", expense_data, expenses_columns
                    )

            if documents_exists and seed_orders:
                docs_dir = _load_documents_dir()
                doc_candidates = [
                    order
                    for order in seed_orders
                    if order.status != RentalStatus.CANCELED
                ]
                rng.shuffle(doc_candidates)
                for order in doc_candidates[: max(6, len(doc_candidates) // 12)]:
                    doc_type = (
                        DocumentType.RECEIPT
                        if order.payment_status == PaymentStatus.PAID
                        else DocumentType.CONTRACT
                    )
                    file_name = build_document_filename(
                        order.customer.name,
                        order.rental.event_date,
                        doc_type,
                    )
                    output_path = docs_dir / file_name
                    generate_rental_pdf(
                        (order.rental, order.items, order.customer),
                        output_path,
                        kind=doc_type.value,
                    )
                    document = Document(
                        id=None,
                        created_at=now,
                        doc_type=doc_type,
                        customer_name=order.customer.name,
                        reference_date=order.rental.event_date,
                        file_name=output_path.name,
                        file_path=str(output_path),
                        order_id=order.rental_id,
                        notes=f"{SEED_TAG} gerado automaticamente",
                    )
                    _insert_row(
                        connection,
                        "documents",
                        {
                            "created_at": document.created_at,
                            "type": document.doc_type.value,
                            "customer_name": document.customer_name,
                            "reference_date": document.reference_date,
                            "file_name": document.file_name,
                            "file_path": document.file_path,
                            "order_id": document.order_id,
                            "notes": document.notes,
                        },
                        documents_columns,
                    )
                    document_count += 1

            connection.commit()
        except Exception:
            connection.rollback()
            raise

        print("\nSeed concluído com sucesso:")
        print(f"Produtos seed: {len(seed_products)}")
        print(f"Clientes seed: {len(customer_ids)}")
        print(f"Pedidos seed: {rental_count}")
        print(f"Itens de pedido seed: {rental_item_count}")
        if payments_exists:
            print(f"Pagamentos seed: {payment_count}")
        if documents_exists:
            print(f"Documentos seed: {document_count}")
        print(f"Receita total gerada: R$ {total_revenue:,.2f}")
        print(f"Período: {start_window.isoformat()} até {today.isoformat()}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
