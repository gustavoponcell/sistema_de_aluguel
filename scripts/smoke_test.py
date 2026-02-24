"""Smoke test for core business flows."""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from rental_manager.db.connection import get_connection  # noqa: E402
from rental_manager.db.migrations import apply_migrations  # noqa: E402
from rental_manager.domain.models import (  # noqa: E402
    Document,
    DocumentType,
    ProductKind,
)
from rental_manager.repositories.customer_repo import CustomerRepo  # noqa: E402
from rental_manager.repositories.document_repo import DocumentRepository  # noqa: E402
from rental_manager.repositories.product_repo import ProductRepo  # noqa: E402
from rental_manager.repositories import rental_repo  # noqa: E402
from rental_manager.services.expense_service import ExpenseService  # noqa: E402
from rental_manager.services.payment_service import PaymentService  # noqa: E402
from rental_manager.services.rental_service import RentalService  # noqa: E402
from rental_manager.utils.pdf_generator import generate_rental_pdf  # noqa: E402


def _build_pdf_payload(connection, customer_repo, product_repo, rental_id: int):
    rental_data = rental_repo.get_rental_with_items(rental_id, connection=connection)
    if not rental_data:
        raise RuntimeError("Pedido não encontrado para gerar PDF.")
    rental, items = rental_data
    customer = customer_repo.get_by_id(rental.customer_id)
    if not customer:
        raise RuntimeError("Cliente não encontrado para gerar PDF.")
    products = product_repo.list_all()
    product_map = {product.id: product for product in products}
    items_for_pdf = [
        SimpleNamespace(
            product_id=item.product_id,
            product_name=product_map.get(item.product_id).name
            if product_map.get(item.product_id)
            else f"Item {item.product_id}",
            qty=item.qty,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        for item in items
    ]
    return rental, items_for_pdf, customer


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = temp_path / "smoke_test.db"
        connection = get_connection(db_path)
        try:
            apply_migrations(connection)

            customer_repo = CustomerRepo(connection)
            product_repo = ProductRepo(connection)
            rental_service = RentalService(connection)
            payment_service = PaymentService(connection)
            expense_service = ExpenseService(connection)
            document_repo = DocumentRepository(connection)

            customer = customer_repo.create(
                name="Cliente Smoke",
                phone="(11) 90000-0000",
                notes="Smoke test",
            )

            rental_product = product_repo.create(
                name="Cadeira Smoke",
                category="Mobiliário",
                total_qty=10,
                unit_price=50.0,
                kind=ProductKind.RENTAL,
                active=True,
            )
            sale_product = product_repo.create(
                name="Copo Descartável",
                category="Venda",
                total_qty=5,
                unit_price=2.5,
                kind=ProductKind.SALE,
                active=True,
            )
            service_product = product_repo.create(
                name="Montagem",
                category="Serviço",
                total_qty=1,
                unit_price=120.0,
                kind=ProductKind.SERVICE,
                active=True,
            )

            today = date.today()
            start_date = today + timedelta(days=1)
            end_date = start_date + timedelta(days=1)
            rental = rental_service.create_draft_rental(
                customer_id=customer.id or 0,
                event_date=start_date.isoformat(),
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                address="Rua Teste, 123",
                contact_phone=customer.phone,
                delivery_required=True,
                items=[
                    {
                        "product_id": rental_product.id or 0,
                        "qty": 2,
                        "unit_price": 50.0,
                    }
                ],
                total_value=None,
            )
            rental_service.confirm_rental(rental.id or 0)

            payment_service.add_payment(
                rental_id=rental.id or 0,
                amount=50.0,
                method="Pix",
                paid_at=today.isoformat(),
                note="Sinal",
            )

            sale_order = rental_service.create_draft_rental(
                customer_id=customer.id or 0,
                event_date=today.isoformat(),
                start_date=None,
                end_date=None,
                address=None,
                contact_phone=customer.phone,
                delivery_required=False,
                items=[
                    {
                        "product_id": sale_product.id or 0,
                        "qty": 2,
                        "unit_price": 2.5,
                    }
                ],
                total_value=None,
            )
            rental_service.confirm_rental(sale_order.id or 0)
            rental_service.complete_rental(sale_order.id or 0)

            service_order = rental_service.create_draft_rental(
                customer_id=customer.id or 0,
                event_date=today.isoformat(),
                start_date=None,
                end_date=None,
                address=None,
                contact_phone=customer.phone,
                delivery_required=False,
                items=[
                    {
                        "product_id": service_product.id or 0,
                        "qty": 1,
                        "unit_price": 120.0,
                    }
                ],
                total_value=None,
            )
            rental_service.confirm_rental(service_order.id or 0)

            expense_service.create_expense(
                date=today.isoformat(),
                category="Operacional",
                description="Gasolina",
                amount=30.0,
                payment_method="Dinheiro",
                supplier="Posto X",
                notes="Viagem para entrega",
            )

            rental_payload = _build_pdf_payload(
                connection, customer_repo, product_repo, rental.id or 0
            )
            output_path = temp_path / "Contrato_Smoke.pdf"
            generate_rental_pdf(rental_payload, output_path, kind="contract")
            document_repo.add(
                Document(
                    id=None,
                    created_at=today.isoformat(),
                    doc_type=DocumentType.CONTRACT,
                    customer_name=customer.name,
                    reference_date=rental.event_date,
                    file_name=output_path.name,
                    file_path=str(output_path),
                    order_id=rental.id,
                    notes="Smoke test",
                )
            )

            start_period = today - timedelta(days=1)
            end_period = today + timedelta(days=7)
            rental_repo.get_finance_report_by_period(
                start_period.isoformat(),
                end_period.isoformat(),
                connection=connection,
            )
            rental_repo.list_rentals_by_period(
                start_period.isoformat(),
                end_period.isoformat(),
                connection=connection,
            )
            expense_service.get_total_by_period(
                start_period.isoformat(),
                end_period.isoformat(),
            )
        finally:
            connection.close()

    print("OK")


if __name__ == "__main__":
    main()
