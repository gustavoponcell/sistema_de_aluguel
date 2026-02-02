"""PDF generation utilities for rentals."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from rental_manager.config import PDF_ISSUER, PdfIssuerInfo
from rental_manager.domain.models import Customer, Rental, RentalItem


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value


def generate_rental_pdf(
    rental_with_items: tuple[Rental, Iterable[RentalItem], Customer],
    output_path: Path,
    *,
    kind: str = "contract",
    issuer: PdfIssuerInfo = PDF_ISSUER,
) -> Path:
    """Generate a rental PDF (contract or receipt)."""
    rental, items, customer = rental_with_items
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Contrato de Locação" if kind == "contract" else "Recibo",
        author=issuer.name,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading3"],
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
        )
    )

    elements: list[object] = []
    title = "CONTRATO DE LOCAÇÃO" if kind == "contract" else "RECIBO"
    elements.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    elements.append(Spacer(1, 8))

    issuer_lines = [
        f"<b>Locador:</b> {issuer.name}",
        f"<b>Contato:</b> {issuer.phone}",
        f"<b>Documento:</b> {issuer.document}",
        f"<b>Endereço:</b> {issuer.address}",
    ]
    elements.append(Paragraph("<br/>".join(issuer_lines), styles["Normal"]))
    elements.append(Spacer(1, 10))

    customer_lines = [
        "<b>Cliente</b>",
        f"Nome: {customer.name}",
        f"Telefone: {customer.phone or '—'}",
    ]
    elements.append(Paragraph("<br/>".join(customer_lines), styles["Normal"]))
    elements.append(Spacer(1, 10))

    dates_table = Table(
        [
            ["Data do evento", _format_date(rental.event_date)],
            ["Retirada/Entrega", _format_date(rental.start_date)],
            ["Devolução", _format_date(rental.end_date)],
            ["Endereço", rental.address or "—"],
        ],
        colWidths=[40 * mm, 120 * mm],
    )
    dates_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ]
        )
    )
    elements.append(Paragraph("Dados do aluguel", styles["SectionTitle"]))
    elements.append(dates_table)
    elements.append(Spacer(1, 12))

    items_data = [["Item", "Qtd", "Valor unit.", "Total"]]
    for item in items:
        name = getattr(item, "product_name", None) or getattr(item, "name", None)
        label = name or f"Produto {item.product_id}"
        items_data.append(
            [
                label,
                str(item.qty),
                _format_currency(item.unit_price),
                _format_currency(item.line_total),
            ]
        )

    items_table = Table(items_data, colWidths=[80 * mm, 18 * mm, 35 * mm, 35 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(Paragraph("Itens locados", styles["SectionTitle"]))
    elements.append(items_table)
    elements.append(Spacer(1, 12))

    saldo = rental.total_value - rental.paid_value
    values_table = Table(
        [
            ["Total", _format_currency(rental.total_value)],
            ["Pago", _format_currency(rental.paid_value)],
            ["Saldo", _format_currency(saldo)],
        ],
        colWidths=[40 * mm, 50 * mm],
    )
    values_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ]
        )
    )
    elements.append(Paragraph("Valores", styles["SectionTitle"]))
    elements.append(values_table)
    elements.append(Spacer(1, 12))

    terms = (
        "O cliente se responsabiliza pela guarda e conservação dos itens durante o "
        "período do aluguel, devendo devolver todos os itens limpos e sem danos na "
        "data combinada. Em caso de avarias ou perda, os custos de reposição serão "
        "cobrados conforme orçamento. Alterações de data devem ser comunicadas com "
        "antecedência."
    )
    elements.append(Paragraph("Termos", styles["SectionTitle"]))
    elements.append(Paragraph(terms, styles["SmallText"]))
    elements.append(Spacer(1, 18))

    signature_table = Table(
        [
            ["Locador", "Cliente"],
            ["_____________________________", "_____________________________"],
        ],
        colWidths=[80 * mm, 80 * mm],
    )
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(signature_table)

    doc.build(elements)
    return output_path
