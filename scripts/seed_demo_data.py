"""Seed demo data into the RentalManager SQLite database."""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rental_manager.db.connection import get_connection
from rental_manager.db.schema import init_db
from rental_manager.paths import get_db_path
from rental_manager.services.inventory_service import InventoryService

SEED_TAG = "Seed Demo"
DEFAULT_SEED = 42


@dataclass(frozen=True)
class ProductSeed:
    key: str
    name: str
    category: str
    total_qty: int
    unit_price: float
    is_service: bool


@dataclass
class PaymentSeed:
    amount: float
    method: str
    paid_at: datetime


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo data for RentalManager")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Limpa dados existentes antes de inserir novos.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não grava dados, apenas simula.",
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
        "active": 1,
        "created_at": now,
        "updated_at": now,
    }
    if "product_type" in columns:
        data["product_type"] = "service" if product.is_service else "physical"
    return _insert_row(connection, "products", data, columns)


def _load_seed_products() -> list[ProductSeed]:
    return [
        ProductSeed(
            key="chairs",
            name=f"{SEED_TAG} - Cadeiras",
            category="cadeira",
            total_qty=200,
            unit_price=2.5,
            is_service=False,
        ),
        ProductSeed(
            key="tables",
            name=f"{SEED_TAG} - Mesas",
            category="mesa",
            total_qty=40,
            unit_price=8.0,
            is_service=False,
        ),
        ProductSeed(
            key="jump",
            name=f"{SEED_TAG} - Pula-pula",
            category="brinquedo",
            total_qty=2,
            unit_price=350.0,
            is_service=False,
        ),
        ProductSeed(
            key="ball_pool",
            name=f"{SEED_TAG} - Piscina de bolinhas",
            category="brinquedo",
            total_qty=1,
            unit_price=280.0,
            is_service=False,
        ),
        ProductSeed(
            key="sound",
            name=f"{SEED_TAG} - Caixa de som",
            category="som",
            total_qty=3,
            unit_price=120.0,
            is_service=False,
        ),
        ProductSeed(
            key="lighting",
            name=f"{SEED_TAG} - Iluminação",
            category="luz",
            total_qty=2,
            unit_price=150.0,
            is_service=False,
        ),
        ProductSeed(
            key="tablecloth",
            name=f"{SEED_TAG} - Toalhas de mesa",
            category="decoracao",
            total_qty=60,
            unit_price=3.0,
            is_service=False,
        ),
        ProductSeed(
            key="face_painting",
            name=f"{SEED_TAG} - Pintura facial",
            category="servico",
            total_qty=9999,
            unit_price=150.0,
            is_service=True,
        ),
        ProductSeed(
            key="animator",
            name=f"{SEED_TAG} - Animadores de festa",
            category="servico",
            total_qty=9999,
            unit_price=300.0,
            is_service=True,
        ),
        ProductSeed(
            key="popcorn",
            name=f"{SEED_TAG} - Carrinho de pipoca",
            category="servico",
            total_qty=9999,
            unit_price=250.0,
            is_service=True,
        ),
        ProductSeed(
            key="cotton_candy",
            name=f"{SEED_TAG} - Carrinho de algodão doce",
            category="servico",
            total_qty=9999,
            unit_price=230.0,
            is_service=True,
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
    neighborhoods = [
        "Centro",
        "Jardim Primavera",
        "Vila Nova",
        "Bela Vista",
        "Parque das Flores",
        "Alto do Lago",
        "Santa Clara",
        "Jardim das Acácias",
        "Cidade Nova",
        "Boa Esperança",
    ]
    cities = ["São Paulo", "Campinas", "Guarulhos", "Osasco", "Santo André"]

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
                "bairro": rng.choice(neighborhoods),
                "cidade": rng.choice(cities),
            }
        )
    return customers


def _random_address(rng: random.Random, customer: dict) -> str:
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
    number = rng.randint(20, 999)
    bairro = customer.get("bairro") or "Centro"
    cidade = customer.get("cidade") or "São Paulo"
    street = rng.choice(streets)
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
                "is_service": product["is_service"],
            }
        )

    add_item("chairs", rng.randint(30, 180))
    add_item("tables", rng.randint(5, 30))

    if rng.random() < 0.35:
        add_item("jump", rng.randint(1, 1))
    if rng.random() < 0.25:
        add_item("ball_pool", rng.randint(1, 1))
    if rng.random() < 0.4:
        add_item("sound", rng.randint(1, 2))
    if rng.random() < 0.3:
        add_item("lighting", rng.randint(1, 2))
    if rng.random() < 0.5:
        add_item("tablecloth", rng.randint(10, 60))

    services = ["face_painting", "animator", "popcorn", "cotton_candy"]
    rng.shuffle(services)
    for service_key in services[: rng.randint(0, 2)]:
        add_item(service_key, 1)

    return items


def _pick_status(rng: random.Random) -> str:
    return rng.choices(
        ["draft", "confirmed", "completed", "canceled"],
        weights=[20, 45, 25, 10],
        k=1,
    )[0]


def _build_payments(
    rng: random.Random,
    status: str,
    total_value: float,
    start: date,
    end: date,
) -> tuple[float, list[PaymentSeed]]:
    if status == "canceled" or total_value <= 0:
        return 0.0, []

    if status == "draft":
        paid_total = rng.choice([0.0, round(total_value * 0.2, 2)])
    else:
        if rng.random() < 0.5:
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
            rng.choice(
                list(
                    _date_range(
                        start - timedelta(days=5), end + timedelta(days=5)
                    )
                )
            ),
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


def _payment_status(paid_value: float, total_value: float) -> str:
    if paid_value <= 0:
        return "unpaid"
    if paid_value + 0.01 < total_value:
        return "partial"
    return "paid"


def _confirm_or_exit(db_path: Path) -> None:
    response = input(
        f"\nConfirma inserir dados no banco {db_path}? (digite 'sim' para continuar): "
    ).strip().lower()
    if response not in {"sim", "s", "yes", "y"}:
        print("Operação cancelada pelo usuário.")
        raise SystemExit(1)


def _clear_tables(connection: sqlite3.Connection, tables: set[str]) -> None:
    ordered_tables = [
        "rental_items",
        "payments",
        "documents",
        "rentals",
        "customers",
        "products",
    ]
    for table in ordered_tables:
        if table in tables:
            connection.execute(f"DELETE FROM {table}")


def main() -> None:
    args = _parse_args()
    rng = random.Random(args.seed)

    db_path = get_db_path()
    print(f"Usando banco de dados: {db_path}")

    init_db(db_path)
    connection = get_connection(db_path)
    try:
        tables = _get_tables(connection)
        if "products" not in tables or "rentals" not in tables:
            raise RuntimeError("Schema inválido: tabelas principais ausentes.")

        product_columns = _get_columns(connection, "products")
        customer_columns = _get_columns(connection, "customers")
        rental_columns = _get_columns(connection, "rentals")
        rental_item_columns = _get_columns(connection, "rental_items")
        payments_exists = "payments" in tables
        payments_columns = _get_columns(connection, "payments") if payments_exists else set()

        existing_rentals = connection.execute(
            "SELECT COUNT(*) FROM rentals WHERE address LIKE ?",
            (f"{SEED_TAG}%",),
        ).fetchone()
        has_seed_rentals = int(existing_rentals[0]) > 0

        if has_seed_rentals and not args.reset:
            print(
                "Dados de seed já encontrados. Nenhum novo aluguel será criado sem --reset."
            )
            return

        if args.reset and args.dry_run:
            print("Aviso: --reset ignorado em dry-run.")

        if not args.dry_run:
            _confirm_or_exit(db_path)

        now = datetime.now().isoformat(timespec="seconds")

        seed_products = _load_seed_products()
        product_map: dict[str, dict] = {}

        today = date.today()
        start_window = today - timedelta(days=60)
        date_candidates = [
            start_window + timedelta(days=offset)
            for offset in range((today - start_window).days + 1)
        ]

        rental_target = rng.randint(120, 250)
        max_attempts = rental_target * 5

        rental_count = 0
        rental_item_count = 0
        payment_count = 0
        total_revenue = 0.0

        try:
            connection.execute("BEGIN")
            if args.reset and not args.dry_run:
                _clear_tables(connection, tables)

            for product in seed_products:
                product_id = _maybe_insert_product(
                    connection, product, product_columns, now
                )
                product_map[product.key] = {
                    "id": product_id,
                    "unit_price": product.unit_price,
                    "is_service": product.is_service,
                    "total_qty": product.total_qty,
                }

            existing_customers = connection.execute(
                "SELECT id, name FROM customers WHERE name LIKE ?",
                (f"{SEED_TAG}%",),
            ).fetchall()
            customer_ids = [int(row["id"]) for row in existing_customers]
            if not customer_ids:
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

            inventory = InventoryService(connection)
            product_totals = {
                info["id"]: info["total_qty"] for info in product_map.values()
            }

            attempts = 0
            while rental_count < rental_target and attempts < max_attempts:
                attempts += 1
                start_date = _pick_start_date(rng, date_candidates)
                duration = _pick_duration(rng)
                end_date = start_date + timedelta(days=duration)
                status = _pick_status(rng)
                customer_id = rng.choice(customer_ids)
                customer_stub = {
                    "bairro": rng.choice(
                        [
                            "Centro",
                            "Jardim Primavera",
                            "Vila Nova",
                            "Bela Vista",
                            "Parque das Flores",
                        ]
                    ),
                    "cidade": rng.choice(
                        ["São Paulo", "Campinas", "Guarulhos", "Osasco", "Santo André"]
                    ),
                }
                address = _random_address(rng, customer_stub)

                items = _build_rental_items(rng, product_map)
                items = _adjust_items_for_availability(
                    inventory, items, product_totals, start_date, end_date
                )
                if not items:
                    continue

                try:
                    inventory.validate_rental_availability(
                        rental_id=None,
                        items=[(item["product_id"], item["qty"]) for item in items],
                        start_date=start_date,
                        end_date=end_date,
                    )
                except ValueError:
                    continue

                total_value = round(sum(item["line_total"] for item in items), 2)
                paid_value, payment_seeds = _build_payments(
                    rng, status, total_value, start_date, end_date
                )
                payment_status = _payment_status(paid_value, total_value)

                rental_data = {
                    "customer_id": customer_id,
                    "event_date": start_date.isoformat(),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "address": address,
                    "status": status,
                    "total_value": total_value,
                    "paid_value": paid_value,
                    "payment_status": payment_status,
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

                total_revenue += total_value

            if rental_count < rental_target:
                print(
                    "Aviso: apenas "
                    f"{rental_count} aluguéis gerados por falta de estoque."
                )

            if args.dry_run:
                connection.rollback()
            else:
                connection.commit()
        except Exception:
            connection.rollback()
            raise

        if args.dry_run:
            print("\nResumo (dry-run):")
            print(f"Produtos seed: {len(seed_products)}")
            print(f"Clientes seed: {len(customer_ids)}")
            print(f"Aluguéis seed: {rental_count}")
            print(f"Pagamentos seed: {payment_count if payments_exists else 0}")
            print(f"Receita estimada: R$ {total_revenue:,.2f}")
            print(f"Período: {start_window.isoformat()} até {today.isoformat()}")
            return

        print("\nSeed concluído com sucesso:")
        print(f"Produtos seed: {len(seed_products)}")
        print(f"Clientes seed: {len(customer_ids)}")
        print(f"Aluguéis seed: {rental_count}")
        print(f"Itens de aluguel seed: {rental_item_count}")
        if payments_exists:
            print(f"Pagamentos seed: {payment_count}")
        print(f"Receita total gerada: R$ {total_revenue:,.2f}")
        print(f"Período: {start_window.isoformat()} até {today.isoformat()}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
