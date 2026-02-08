"""PDF generation utilities for orders."""

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
from rental_manager.domain.models import (
    Customer,
    DocumentType,
    ProductKind,
    Rental,
    RentalItem,
)


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value


def _kind_label(kind: ProductKind) -> str:
    return {
        ProductKind.RENTAL: "Aluguel",
        ProductKind.SALE: "Venda",
        ProductKind.SERVICE: "Serviço",
    }.get(kind, "Aluguel")


def _document_title(doc_type: DocumentType, kind: ProductKind) -> str:
    if doc_type == DocumentType.CONTRACT:
        return {
            ProductKind.RENTAL: "CONTRATO DE LOCAÇÃO",
            ProductKind.SALE: "COMPROVANTE DE VENDA",
            ProductKind.SERVICE: "ORDEM DE SERVIÇO",
        }.get(kind, "CONTRATO DE LOCAÇÃO")
    return f"RECIBO DE PAGAMENTO ({_kind_label(kind).upper()})"


def _build_order_rows(rental: Rental, kind: ProductKind) -> list[list[str]]:
    address = rental.address
    if not address:
        if kind == ProductKind.SALE:
            address = "Retirada no local"
        elif kind == ProductKind.SERVICE:
            address = "Local a combinar"
        else:
            address = "Retirada no local"

    if kind == ProductKind.RENTAL:
        return [
            ["Data do pedido", _format_date(rental.event_date)],
            ["Retirada/Entrega", _format_date(rental.start_date)],
            ["Devolução", _format_date(rental.end_date)],
            ["Entrega", "Sim" if rental.delivery_required else "Retirada"],
            ["Endereço", address],
        ]

    if kind == ProductKind.SALE:
        return [
            ["Data da venda", _format_date(rental.event_date)],
            ["Entrega", "Sim" if rental.delivery_required else "Retirada"],
            ["Endereço", address],
        ]

    rows = [["Data do serviço", _format_date(rental.event_date)]]
    if rental.start_date:
        rows.append(["Início", _format_date(rental.start_date)])
    if rental.end_date:
        rows.append(["Fim", _format_date(rental.end_date)])
    rows.append(["Local", address])
    return rows


def _build_terms(doc_type: DocumentType, kind: ProductKind) -> str:
    if doc_type == DocumentType.RECEIPT:
        return (
            "Declaramos que recebemos os valores descritos neste documento, "
            "referentes ao pedido informado. Este recibo comprova o pagamento "
            "do cliente pelos itens/serviços listados."
        )
    if kind == ProductKind.SALE:
        return (
            "Os itens vendidos foram conferidos no momento da entrega/retirada. "
            "Eventuais ajustes ou devoluções devem ser comunicados imediatamente."
        )
    if kind == ProductKind.SERVICE:
        return (
            "O serviço será executado conforme combinado entre as partes. "
            "Qualquer alteração de data ou local deve ser avisada com antecedência."
        )
    return (
        "O cliente se responsabiliza pela guarda e conservação dos itens durante o "
        "período do pedido, devendo devolver todos os itens limpos e sem danos na "
        "data combinada. Em caso de avarias ou perda, os custos de reposição serão "
        "cobrados conforme orçamento. Alterações de data devem ser comunicadas com "
        "antecedência."
    )


def generate_document_pdf(
    rental_with_items: tuple[Rental, Iterable[RentalItem], Customer],
    output_path: Path,
    *,
    doc_type: DocumentType,
    order_kind: ProductKind,
    issuer: PdfIssuerInfo = PDF_ISSUER,
) -> Path:
    """Generate a PDF document for the given order kind."""
    rental, items, customer = rental_with_items
    output_path.parent.mkdir(parents=True, exist_ok=True)

    title = _document_title(doc_type, order_kind)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
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
    main_title = f"{customer.name} - {_format_date(rental.event_date)}"
    elements.append(Paragraph(f"<b>{main_title}</b>", styles["Title"]))
    elements.append(Paragraph(title, styles["Heading2"]))
    elements.append(Spacer(1, 8))

    issuer_lines = [
        f"<b>Responsável:</b> {issuer.name}",
        f"<b>Contato:</b> {issuer.phone}",
        f"<b>Documento:</b> {issuer.document}",
        f"<b>Endereço:</b> {issuer.address}",
    ]
    elements.append(Paragraph("<br/>".join(issuer_lines), styles["Normal"]))
    elements.append(Spacer(1, 10))

    contact_phone = rental.contact_phone or customer.phone
    customer_lines = [
        "<b>Cliente</b>",
        f"Nome: {customer.name}",
        f"Telefone: {contact_phone or '—'}",
        "Documento: —",
    ]
    elements.append(Paragraph("<br/>".join(customer_lines), styles["Normal"]))
    elements.append(Spacer(1, 10))

    order_rows = _build_order_rows(rental, order_kind)
    dates_table = Table(order_rows, colWidths=[40 * mm, 120 * mm])
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
    elements.append(Paragraph("Dados do pedido", styles["SectionTitle"]))
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
    elements.append(Paragraph("Itens do pedido", styles["SectionTitle"]))
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

    terms = _build_terms(doc_type, order_kind)
    elements.append(Paragraph("Termos", styles["SectionTitle"]))
    elements.append(Paragraph(terms, styles["SmallText"]))
    elements.append(Spacer(1, 18))

    signature_table = Table(
        [
            ["Responsável", "Cliente"],
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

    footer = (
        f"Gestão Inteligente — gerado em "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(footer, styles["SmallText"]))

    doc.build(elements)
    return output_path


def generate_rental_pdf(
    rental_with_items: tuple[Rental, Iterable[RentalItem], Customer],
    output_path: Path,
    *,
    kind: str = "contract",
    issuer: PdfIssuerInfo = PDF_ISSUER,
) -> Path:
    """Backward-compatible wrapper for PDF generation."""
    try:
        doc_type = DocumentType(kind)
    except ValueError:
        doc_type = DocumentType.CONTRACT
    return generate_document_pdf(
        rental_with_items,
        output_path,
        doc_type=doc_type,
        order_kind=ProductKind.RENTAL,
        issuer=issuer,
    )
