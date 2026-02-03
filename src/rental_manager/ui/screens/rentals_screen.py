"""Screen for rentals agenda."""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.domain.models import (
    Customer,
    Document,
    DocumentType,
    Payment,
    PaymentStatus,
    Rental,
    RentalItem,
    RentalStatus,
)
from rental_manager.paths import get_pdfs_dir
from rental_manager.repositories import rental_repo
from rental_manager.services.errors import ValidationError
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.utils.pdf_generator import generate_rental_pdf
from rental_manager.ui.widgets import InfoBanner


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_date(value: str) -> str:
    parsed = QtCore.QDate.fromString(value, "yyyy-MM-dd")
    return parsed.toString("dd/MM/yyyy") if parsed.isValid() else value


def _format_datetime(value: Optional[str]) -> str:
    if not value:
        return "—"
    parsed = QtCore.QDateTime.fromString(value, "yyyy-MM-ddTHH:mm:ss")
    if not parsed.isValid():
        parsed = QtCore.QDateTime.fromString(value, "yyyy-MM-dd HH:mm:ss")
    if parsed.isValid():
        return parsed.toString("dd/MM/yyyy HH:mm")
    parsed_date = QtCore.QDate.fromString(value, "yyyy-MM-dd")
    return parsed_date.toString("dd/MM/yyyy") if parsed_date.isValid() else value


def _summarize_address(address: Optional[str], max_len: int = 42) -> str:
    if not address:
        return "—"
    cleaned = " ".join(address.split())
    return cleaned if len(cleaned) <= max_len else f"{cleaned[: max_len - 3]}..."


def _status_label(status: RentalStatus) -> str:
    mapping = {
        RentalStatus.DRAFT: "Rascunho",
        RentalStatus.CONFIRMED: "Confirmado",
        RentalStatus.CANCELED: "Cancelado",
        RentalStatus.COMPLETED: "Concluído",
    }
    return mapping.get(status, status.value)


def _payment_label(status: PaymentStatus) -> str:
    mapping = {
        PaymentStatus.UNPAID: "Pendente",
        PaymentStatus.PARTIAL: "Parcial",
        PaymentStatus.PAID: "Pago",
    }
    return mapping.get(status, status.value)


def _show_warning(parent: QtWidgets.QWidget, message: str) -> None:
    QtWidgets.QMessageBox.warning(parent, "Atenção", message)


def _show_error(parent: QtWidgets.QWidget, message: str) -> None:
    QtWidgets.QMessageBox.critical(parent, "Erro", message)


def _show_success(parent: QtWidgets.QWidget, message: str) -> None:
    QtWidgets.QMessageBox.information(parent, "Sucesso", message)


def _confirm_action(parent: QtWidgets.QWidget, message: str) -> bool:
    response = QtWidgets.QMessageBox.question(
        parent,
        "Confirmação",
        message,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
    )
    return response == QtWidgets.QMessageBox.Yes


@dataclass
class RentalItemDraft:
    """Draft item for editing rentals."""

    product_id: int
    product_name: str
    qty: int
    unit_price: float

    @property
    def line_total(self) -> float:
        return self.qty * self.unit_price


class RentalDetailsDialog(QtWidgets.QDialog):
    """Dialog to show rental details."""

    def __init__(self, services: AppServices, rental_id: int) -> None:
        super().__init__()
        self._services = services
        self._rental_id = rental_id
        self._rental: Optional[Rental] = None
        self._items: List[RentalItem] = []
        self.setWindowTitle("Detalhes do aluguel")
        self.setModal(True)
        self._load_data()
        self._build_ui()

    def _load_data(self) -> None:
        try:
            rental_data = rental_repo.get_rental_with_items(
                self._rental_id,
                connection=self._services.connection,
            )
        except Exception:
            rental_data = None
        if rental_data:
            self._rental, self._items = rental_data

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)
        if not self._rental:
            layout.addWidget(
                QtWidgets.QLabel("Aluguel não encontrado para exibir os detalhes.")
            )
            close_button = QtWidgets.QPushButton("Fechar")
            close_button.clicked.connect(self.reject)
            layout.addWidget(close_button)
            return

        try:
            customer = self._services.customer_repo.get_by_id(self._rental.customer_id)
            products = self._services.product_repo.list_all()
            product_map = {product.id: product for product in products}
        except Exception:
            customer = None
            product_map = {}

        info_group = QtWidgets.QGroupBox("Dados do aluguel")
        info_layout = QtWidgets.QFormLayout(info_group)

        info_layout.addRow("Cliente:", QtWidgets.QLabel(customer.name if customer else "—"))
        info_layout.addRow(
            "Telefone:",
            QtWidgets.QLabel(customer.phone if customer and customer.phone else "—"),
        )
        info_layout.addRow("Evento:", QtWidgets.QLabel(_format_date(self._rental.event_date)))
        info_layout.addRow("Início:", QtWidgets.QLabel(_format_date(self._rental.start_date)))
        info_layout.addRow("Fim:", QtWidgets.QLabel(_format_date(self._rental.end_date)))
        info_layout.addRow(
            "Status:", QtWidgets.QLabel(_status_label(self._rental.status))
        )
        self._payment_status_label = QtWidgets.QLabel(
            _payment_label(self._rental.payment_status)
        )
        info_layout.addRow("Pagamento:", self._payment_status_label)
        info_layout.addRow(
            "Total:", QtWidgets.QLabel(_format_currency(self._rental.total_value))
        )
        self._paid_value_label = QtWidgets.QLabel(
            _format_currency(self._rental.paid_value)
        )
        info_layout.addRow("Pago:", self._paid_value_label)
        info_layout.addRow(
            "Endereço:",
            QtWidgets.QLabel(self._rental.address or "—"),
        )

        layout.addWidget(info_group)

        items_group = QtWidgets.QGroupBox("Itens")
        items_layout = QtWidgets.QVBoxLayout(items_group)
        items_table = QtWidgets.QTableWidget(0, 4)
        items_table.setHorizontalHeaderLabels(
            ["Produto", "Quantidade", "Preço unitário", "Total"]
        )
        items_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        items_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        items_table.verticalHeader().setVisible(False)
        header = items_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)

        items_table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            product_name = (
                product_map.get(item.product_id).name
                if item.product_id in product_map
                else "—"
            )
            items_table.setItem(row, 0, QtWidgets.QTableWidgetItem(product_name))
            items_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(item.qty)))
            items_table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(_format_currency(item.unit_price))
            )
            items_table.setItem(
                row, 3, QtWidgets.QTableWidgetItem(_format_currency(item.line_total))
            )
        items_table.resizeRowsToContents()
        items_layout.addWidget(items_table)
        layout.addWidget(items_group)

        payments_section = PaymentsSection(
            self._services,
            rental_id=self._rental_id,
            on_change=self._refresh_payment_summary,
        )
        layout.addWidget(payments_section)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _refresh_payment_summary(self) -> None:
        try:
            rental_data = rental_repo.get_rental_with_items(
                self._rental_id, connection=self._services.connection
            )
        except Exception:
            rental_data = None
        if not rental_data:
            return
        self._rental, _items = rental_data
        self._payment_status_label.setText(
            _payment_label(self._rental.payment_status)
        )
        self._paid_value_label.setText(_format_currency(self._rental.paid_value))


class PaymentEntryDialog(QtWidgets.QDialog):
    """Dialog to create or edit a payment entry."""

    def __init__(self, title: str, payment: Optional[Payment] = None) -> None:
        super().__init__()
        self._payment = payment
        self.setWindowTitle(title)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.amount_input = QtWidgets.QDoubleSpinBox()
        self.amount_input.setRange(0.0, 1_000_000.0)
        self.amount_input.setDecimals(2)
        self.amount_input.setPrefix("R$ ")
        self.amount_input.setValue(self._payment.amount if self._payment else 0.0)

        self.method_input = QtWidgets.QLineEdit()
        self.method_input.setPlaceholderText("Dinheiro, PIX, cartão...")
        if self._payment and self._payment.method:
            self.method_input.setText(self._payment.method)

        self.paid_at_check = QtWidgets.QCheckBox("Definir data/hora")
        self.paid_at_input = QtWidgets.QDateTimeEdit()
        self.paid_at_input.setCalendarPopup(True)
        self.paid_at_input.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.paid_at_input.setDateTime(QtCore.QDateTime.currentDateTime())
        if self._payment and self._payment.paid_at:
            parsed = QtCore.QDateTime.fromString(
                self._payment.paid_at, "yyyy-MM-ddTHH:mm:ss"
            )
            if not parsed.isValid():
                parsed = QtCore.QDateTime.fromString(
                    self._payment.paid_at, "yyyy-MM-dd HH:mm:ss"
                )
            if not parsed.isValid():
                parsed_date = QtCore.QDate.fromString(
                    self._payment.paid_at, "yyyy-MM-dd"
                )
                if parsed_date.isValid():
                    parsed = QtCore.QDateTime(parsed_date, QtCore.QTime(0, 0))
            if parsed.isValid():
                self.paid_at_input.setDateTime(parsed)
        if self._payment and not self._payment.paid_at:
            self.paid_at_check.setChecked(False)
        else:
            self.paid_at_check.setChecked(True)
        self.paid_at_input.setEnabled(self.paid_at_check.isChecked())
        self.paid_at_check.toggled.connect(self.paid_at_input.setEnabled)

        self.note_input = QtWidgets.QPlainTextEdit()
        self.note_input.setPlaceholderText("Observações sobre o pagamento")
        self.note_input.setFixedHeight(80)
        if self._payment and self._payment.note:
            self.note_input.setPlainText(self._payment.note)

        form.addRow("Valor:", self.amount_input)
        form.addRow("Método:", self.method_input)
        form.addRow("", self.paid_at_check)
        form.addRow("Data/hora:", self.paid_at_input)
        form.addRow("Observação:", self.note_input)
        layout.addLayout(form)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_accept(self) -> None:
        if self.amount_input.value() <= 0:
            _show_warning(self, "Informe um valor maior que zero.")
            return
        self.accept()

    def get_payment_data(self) -> dict[str, Optional[str] | float]:
        paid_at = None
        if self.paid_at_check.isChecked():
            paid_at = self.paid_at_input.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        note = self.note_input.toPlainText().strip() or None
        method = self.method_input.text().strip() or None
        return {
            "amount": float(self.amount_input.value()),
            "method": method,
            "paid_at": paid_at,
            "note": note,
        }


class PaymentsSection(QtWidgets.QGroupBox):
    """Widget section to manage payments for a rental."""

    def __init__(
        self,
        services: AppServices,
        rental_id: int,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__("Pagamentos")
        self._services = services
        self._rental_id = rental_id
        self._on_change = on_change
        self._payments: list[Payment] = []
        self._build_ui()
        self._load_payments()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        actions_layout = QtWidgets.QHBoxLayout()
        add_button = QtWidgets.QPushButton("Adicionar pagamento")
        add_button.clicked.connect(self._on_add_payment)
        actions_layout.addWidget(add_button)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        self._table = QtWidgets.QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Data/hora", "Valor", "Método", "Observação", "Ações"]
        )
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self._table)

    def _load_payments(self) -> None:
        try:
            self._payments = self._services.payment_service.list_payments(
                self._rental_id
            )
        except Exception:
            _show_error(self, "Não foi possível carregar os pagamentos.")
            return

        self._table.setRowCount(0)
        for row_index, payment in enumerate(self._payments):
            self._table.insertRow(row_index)
            self._table.setItem(
                row_index, 0, QtWidgets.QTableWidgetItem(_format_datetime(payment.paid_at))
            )
            self._table.setItem(
                row_index,
                1,
                QtWidgets.QTableWidgetItem(_format_currency(payment.amount)),
            )
            self._table.setItem(
                row_index,
                2,
                QtWidgets.QTableWidgetItem(payment.method or "—"),
            )
            self._table.setItem(
                row_index,
                3,
                QtWidgets.QTableWidgetItem(payment.note or "—"),
            )
            self._table.setCellWidget(
                row_index, 4, self._build_actions_widget(payment)
            )
        self._table.resizeRowsToContents()

    def _build_actions_widget(self, payment: Payment) -> QtWidgets.QWidget:
        actions = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        edit_button = QtWidgets.QPushButton("Editar")
        delete_button = QtWidgets.QPushButton("Excluir")
        edit_button.clicked.connect(
            lambda _checked=False, pid=payment.id: self._on_edit_payment(pid)
        )
        delete_button.clicked.connect(
            lambda _checked=False, pid=payment.id: self._on_delete_payment(pid)
        )
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
        return actions

    def _on_add_payment(self) -> None:
        dialog = PaymentEntryDialog("Adicionar pagamento")
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_payment_data()
        try:
            self._services.payment_service.add_payment(
                rental_id=self._rental_id,
                amount=float(data["amount"]),
                method=data["method"],
                paid_at=data["paid_at"],
                note=data["note"],
            )
        except Exception as exc:
            _show_error(self, str(exc))
            return
        self._notify_change()

    def _on_edit_payment(self, payment_id: Optional[int]) -> None:
        if payment_id is None:
            return
        payment = next((item for item in self._payments if item.id == payment_id), None)
        if not payment:
            _show_warning(self, "Pagamento não encontrado para edição.")
            return
        dialog = PaymentEntryDialog("Editar pagamento", payment=payment)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_payment_data()
        try:
            self._services.payment_service.update_payment(
                payment_id=payment_id,
                amount=float(data["amount"]),
                method=data["method"],
                paid_at=data["paid_at"],
                note=data["note"],
            )
        except Exception as exc:
            _show_error(self, str(exc))
            return
        self._notify_change()

    def _on_delete_payment(self, payment_id: Optional[int]) -> None:
        if payment_id is None:
            return
        if not _confirm_action(self, "Excluir este pagamento?"):
            return
        try:
            self._services.payment_service.delete_payment(payment_id)
        except Exception as exc:
            _show_error(self, str(exc))
            return
        self._notify_change()

    def _notify_change(self) -> None:
        self._load_payments()
        self._services.data_bus.data_changed.emit()
        if self._on_change:
            self._on_change()


class RentalEditDialog(QtWidgets.QDialog):
    """Dialog to edit an existing rental."""

    def __init__(self, services: AppServices, rental_id: int) -> None:
        super().__init__()
        self._services = services
        self._rental_id = rental_id
        self._rental: Optional[Rental] = None
        self._items: List[RentalItemDraft] = []
        self._customers: List[object] = []
        self._products: List[object] = []
        self._editing_index: Optional[int] = None
        self.setWindowTitle("Editar aluguel")
        self.setModal(True)
        self._load_rental()
        self._build_ui()
        if self._rental:
            self._load_customers()
            self._load_products()
            self._load_rental_data()

    def _load_rental(self) -> None:
        try:
            rental_data = rental_repo.get_rental_with_items(
                self._rental_id,
                connection=self._services.connection,
            )
        except Exception:
            rental_data = None
        if rental_data:
            self._rental, items = rental_data
            try:
                products = self._services.product_repo.list_all()
            except Exception:
                products = []
            product_map = {product.id: product for product in products}
            self._items = [
                RentalItemDraft(
                    product_id=item.product_id,
                    product_name=product_map.get(item.product_id).name
                    if item.product_id in product_map
                    else "—",
                    qty=item.qty,
                    unit_price=item.unit_price,
                )
                for item in items
            ]

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        if not self._rental:
            layout.addWidget(QtWidgets.QLabel("Aluguel não encontrado para edição."))
            close_button = QtWidgets.QPushButton("Fechar")
            close_button.clicked.connect(self.reject)
            layout.addWidget(close_button)
            return

        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QtWidgets.QFormLayout()
        form.setVerticalSpacing(12)
        customer_row = QtWidgets.QHBoxLayout()
        self.customer_combo = QtWidgets.QComboBox()
        self.customer_combo.setMinimumWidth(240)
        self.customer_combo.setMinimumHeight(36)
        customer_row.addWidget(self.customer_combo)
        customer_row.addStretch()

        self.event_date_input = QtWidgets.QDateEdit()
        self.event_date_input.setCalendarPopup(True)
        self.event_date_input.setDisplayFormat("dd/MM/yyyy")
        self.start_date_input = QtWidgets.QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("dd/MM/yyyy")
        self.end_date_input = QtWidgets.QDateEdit()
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDisplayFormat("dd/MM/yyyy")
        self.start_date_input.dateChanged.connect(self._sync_end_date_min)
        self.start_date_input.dateChanged.connect(self._on_dates_changed)
        self.end_date_input.dateChanged.connect(self._on_dates_changed)

        dates_row = QtWidgets.QHBoxLayout()
        dates_row.addWidget(QtWidgets.QLabel("Evento"))
        dates_row.addWidget(self.event_date_input)
        dates_row.addSpacing(12)
        dates_row.addWidget(QtWidgets.QLabel("Início"))
        dates_row.addWidget(self.start_date_input)
        dates_row.addSpacing(12)
        dates_row.addWidget(QtWidgets.QLabel("Fim"))
        dates_row.addWidget(self.end_date_input)
        dates_row.addStretch()

        self.address_input = QtWidgets.QPlainTextEdit()
        self.address_input.setFixedHeight(80)
        self.address_input.setPlaceholderText("Rua, número, bairro, referência")

        form.addRow("Cliente:", customer_row)
        form.addRow("Datas:", dates_row)
        form.addRow("Endereço:", self.address_input)

        layout.addLayout(form)

        items_group = QtWidgets.QGroupBox("Itens do aluguel")
        items_layout = QtWidgets.QVBoxLayout(items_group)

        item_form = QtWidgets.QGridLayout()
        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.currentIndexChanged.connect(self._on_product_selected)
        self.qty_input = QtWidgets.QSpinBox()
        self.qty_input.setRange(1, 1_000_000)
        self.unit_price_input = QtWidgets.QDoubleSpinBox()
        self.unit_price_input.setRange(0.0, 1_000_000.0)
        self.unit_price_input.setDecimals(2)
        self.unit_price_input.setSingleStep(1.0)
        self.unit_price_input.setPrefix("R$ ")
        self.add_item_button = QtWidgets.QPushButton("Adicionar item")
        self.add_item_button.setMinimumHeight(40)
        self.add_item_button.clicked.connect(self._on_add_item)

        item_form.addWidget(QtWidgets.QLabel("Produto"), 0, 0)
        item_form.addWidget(QtWidgets.QLabel("Quantidade"), 0, 1)
        item_form.addWidget(QtWidgets.QLabel("Preço unitário"), 0, 2)
        item_form.addWidget(self.product_combo, 1, 0)
        item_form.addWidget(self.qty_input, 1, 1)
        item_form.addWidget(self.unit_price_input, 1, 2)
        item_form.addWidget(self.add_item_button, 1, 3)
        item_form.setColumnStretch(0, 2)
        item_form.setColumnStretch(1, 1)
        item_form.setColumnStretch(2, 1)
        item_form.setColumnStretch(3, 1)

        items_layout.addLayout(item_form)

        self.items_table = QtWidgets.QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(
            ["Produto", "Quantidade", "Preço unitário", "Total", "Ações"]
        )
        self.items_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.items_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.items_table.verticalHeader().setVisible(False)
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)

        items_layout.addWidget(self.items_table)

        total_layout = QtWidgets.QHBoxLayout()
        total_layout.addStretch()
        self.total_label = QtWidgets.QLabel("Total: R$ 0,00")
        self.total_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        total_layout.addWidget(self.total_label)
        items_layout.addLayout(total_layout)

        layout.addWidget(items_group)

        payments_section = PaymentsSection(
            self._services,
            rental_id=self._rental_id,
            on_change=self._refresh_rental_payment,
        )
        layout.addWidget(payments_section)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
            }
            QLineEdit, QDateEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
                font-size: 14px;
                padding: 4px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 14px;
            }
            QGroupBox {
                font-weight: 600;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            """
        )

    def _refresh_rental_payment(self) -> None:
        try:
            rental_data = rental_repo.get_rental_with_items(
                self._rental_id, connection=self._services.connection
            )
        except Exception:
            return
        if rental_data:
            self._rental, _items = rental_data

    def _load_customers(self) -> None:
        try:
            self._customers = self._services.customer_repo.list_all()
        except Exception:
            _show_error(self, "Não foi possível carregar os clientes.")
            return
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("Selecione um cliente", None)
        for customer in self._customers:
            self.customer_combo.addItem(customer.name, customer.id)
        self.customer_combo.blockSignals(False)

    def _load_products(self) -> None:
        try:
            self._products = self._services.product_repo.list_all()
        except Exception:
            _show_error(self, "Não foi possível carregar os produtos.")
            return
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self.product_combo.addItem("Selecione um produto", None)
        for product in self._products:
            self.product_combo.addItem(product.name, product.id)
        self.product_combo.blockSignals(False)
        self._apply_selected_product_price()

    def _load_rental_data(self) -> None:
        if not self._rental:
            return
        customer_index = self.customer_combo.findData(self._rental.customer_id)
        if customer_index >= 0:
            self.customer_combo.setCurrentIndex(customer_index)
        event_date = QtCore.QDate.fromString(self._rental.event_date, "yyyy-MM-dd")
        start_date = QtCore.QDate.fromString(self._rental.start_date, "yyyy-MM-dd")
        end_date = QtCore.QDate.fromString(self._rental.end_date, "yyyy-MM-dd")
        if event_date.isValid():
            self.event_date_input.setDate(event_date)
        if start_date.isValid():
            self.start_date_input.setDate(start_date)
        if end_date.isValid():
            self.end_date_input.setDate(end_date)
        self.address_input.setPlainText(self._rental.address or "")
        self._render_items_table()
        self._update_total_label()
        self._sync_end_date_min(self.start_date_input.date())

    def _on_product_selected(self) -> None:
        self._apply_selected_product_price()

    def _apply_selected_product_price(self) -> None:
        product = self._get_selected_product()
        if not product or product.unit_price is None:
            self.unit_price_input.setValue(0.0)
            return
        self.unit_price_input.setValue(float(product.unit_price))

    def _get_selected_product(self) -> Optional[object]:
        product_id = self.product_combo.currentData()
        if not product_id:
            return None
        for product in self._products:
            if product.id == product_id:
                return product
        return None

    def _get_selected_customer_id(self) -> Optional[int]:
        customer_id = self.customer_combo.currentData()
        return int(customer_id) if customer_id else None

    def _on_add_item(self) -> None:
        product = self._get_selected_product()
        if not product or product.id is None:
            _show_warning(self, "Selecione um produto para adicionar.")
            return
        if not self._validate_dates():
            return
        qty = int(self.qty_input.value())
        unit_price = float(self.unit_price_input.value())
        if qty <= 0:
            _show_warning(self, "Informe uma quantidade maior que zero.")
            return
        if unit_price <= 0:
            _show_warning(self, "Informe um preço unitário válido.")
            return
        updated_items = self._prepare_updated_items(
            product_id=product.id,
            product_name=product.name,
            qty=qty,
            unit_price=unit_price,
        )
        if not self._validate_inventory(updated_items):
            return
        self._items = updated_items
        self._editing_index = None
        self.add_item_button.setText("Adicionar item")
        self.qty_input.setValue(1)
        self._render_items_table()
        self._update_total_label()

    def _prepare_updated_items(
        self, product_id: int, product_name: str, qty: int, unit_price: float
    ) -> List[RentalItemDraft]:
        items = list(self._items)
        if self._editing_index is None:
            for item in items:
                if item.product_id == product_id:
                    item.qty += qty
                    item.unit_price = unit_price
                    return items
            items.append(RentalItemDraft(product_id, product_name, qty, unit_price))
            return items
        if self._editing_index < 0 or self._editing_index >= len(items):
            items.append(RentalItemDraft(product_id, product_name, qty, unit_price))
            return items
        existing = items[self._editing_index]
        existing.product_id = product_id
        existing.product_name = product_name
        existing.qty = qty
        existing.unit_price = unit_price
        for index, item in enumerate(items):
            if index == self._editing_index:
                continue
            if item.product_id == product_id:
                existing.qty += item.qty
                items.pop(index)
                break
        return items

    def _render_items_table(self) -> None:
        self.items_table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.items_table.setItem(
                row, 0, QtWidgets.QTableWidgetItem(item.product_name)
            )
            self.items_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(item.qty)))
            self.items_table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(_format_currency(item.unit_price))
            )
            self.items_table.setItem(
                row, 3, QtWidgets.QTableWidgetItem(_format_currency(item.line_total))
            )
            action_widget = QtWidgets.QWidget()
            action_layout = QtWidgets.QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            edit_button = QtWidgets.QPushButton("Editar")
            remove_button = QtWidgets.QPushButton("Remover")
            edit_button.clicked.connect(lambda _, idx=row: self._on_edit_item(idx))
            remove_button.clicked.connect(
                lambda _, idx=row: self._on_remove_item(idx)
            )
            action_layout.addWidget(edit_button)
            action_layout.addWidget(remove_button)
            action_layout.addStretch()
            self.items_table.setCellWidget(row, 4, action_widget)
        self.items_table.resizeRowsToContents()

    def _on_edit_item(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            return
        item = self._items[index]
        product_index = self.product_combo.findData(item.product_id)
        if product_index >= 0:
            self.product_combo.setCurrentIndex(product_index)
        self.qty_input.setValue(item.qty)
        self.unit_price_input.setValue(item.unit_price)
        self._editing_index = index
        self.add_item_button.setText("Atualizar item")

    def _on_remove_item(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            return
        self._items.pop(index)
        self._editing_index = None
        self.add_item_button.setText("Adicionar item")
        self._render_items_table()
        self._update_total_label()

    def _update_total_label(self) -> None:
        total = sum(item.line_total for item in self._items)
        self.total_label.setText(f"Total: {_format_currency(total)}")

    def _get_dates(self) -> tuple[date, date, date]:
        event_date = self.event_date_input.date().toPython()
        start_date = self.start_date_input.date().toPython()
        end_date = self.end_date_input.date().toPython()
        return event_date, start_date, end_date

    def _sync_end_date_min(self, new_start_date: QtCore.QDate) -> None:
        minimum_end_date = new_start_date.addDays(1)
        self.end_date_input.setMinimumDate(minimum_end_date)
        if self.end_date_input.date() < minimum_end_date:
            self.end_date_input.setDate(minimum_end_date)

    def _on_dates_changed(self) -> None:
        if not self._items:
            return
        if not self._validate_dates():
            return
        self._validate_inventory(self._items)

    def _validate_dates(self) -> bool:
        _event_date, start_date, end_date = self._get_dates()
        if start_date >= end_date:
            _show_warning(
                self, "A data de término deve ser posterior à data de início."
            )
            return False
        return True

    def _validate_form(self) -> bool:
        if not self._get_selected_customer_id():
            _show_warning(self, "Selecione um cliente para o aluguel.")
            return False
        if not self._validate_dates():
            return False
        if not self._items:
            _show_warning(self, "Adicione ao menos um item ao aluguel.")
            return False
        return True

    def _validate_inventory(self, items: List[RentalItemDraft]) -> bool:
        _event_date, start_date, end_date = self._get_dates()
        aggregated = self._aggregate_items(items)
        try:
            self._services.inventory_service.validate_rental_availability(
                self._rental_id,
                aggregated,
                start_date.isoformat(),
                end_date.isoformat(),
            )
        except ValueError as exc:
            _show_warning(self, str(exc))
            return False
        return True

    def _aggregate_items(self, items: List[RentalItemDraft]) -> List[tuple[int, int]]:
        aggregated: dict[int, int] = {}
        for item in items:
            aggregated[item.product_id] = aggregated.get(item.product_id, 0) + item.qty
        return list(aggregated.items())

    def _build_items_payload(self) -> List[dict[str, object]]:
        return [
            {
                "product_id": item.product_id,
                "qty": item.qty,
                "unit_price": item.unit_price,
            }
            for item in self._items
        ]

    def _on_save(self) -> None:
        if not self._rental or not self._validate_form():
            return
        customer_id = self._get_selected_customer_id()
        if customer_id is None:
            return
        event_date, start_date, end_date = self._get_dates()
        items_payload = self._build_items_payload()
        total_value = sum(item.line_total for item in self._items)
        if total_value <= 0 and not _confirm_action(
            self, "O total do aluguel está R$ 0,00. Deseja continuar mesmo assim?"
        ):
            return
        try:
            self._services.rental_service.update_rental(
                rental_id=self._rental_id,
                customer_id=customer_id,
                event_date=event_date.isoformat(),
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                address=self.address_input.toPlainText().strip() or None,
                items=items_payload,
                total_value=total_value,
                status=self._rental.status,
            )
        except ValidationError as exc:
            _show_warning(self, str(exc))
            return
        except Exception:
            _show_error(self, "Não foi possível atualizar o aluguel. Tente novamente.")
            return
        self._services.data_bus.data_changed.emit()
        self.accept()


class RentalsScreen(BaseScreen):
    """Screen for the rentals agenda."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._rentals: List[Rental] = []
        self._customers_map: dict[int, str] = {}
        self._latest_documents: dict[DocumentType, Optional[Document]] = {
            DocumentType.CONTRACT: None,
            DocumentType.RECEIPT: None,
        }
        self._filter_timer = QtCore.QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(250)
        self._filter_timer.timeout.connect(self.refresh)
        self._build_ui()
        self._load_rentals()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Agenda")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Consulte os aluguéis agendados, filtre por datas, status e pagamentos."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #555; font-size: 14px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.today_banner = InfoBanner(
            self._services.theme_manager,
            "Aluguéis de hoje",
            "Nenhum aluguel previsto para hoje.",
            "Assim que houver um aluguel, ele aparece aqui.",
        )
        layout.addWidget(self.today_banner)

        filters_group = QtWidgets.QGroupBox("Filtros")
        filters_layout = QtWidgets.QGridLayout(filters_group)
        filters_layout.setVerticalSpacing(12)
        filters_layout.setHorizontalSpacing(12)

        self.date_filter_check = QtWidgets.QCheckBox("Filtrar por datas")
        self.start_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("dd/MM/yyyy")
        self.end_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDisplayFormat("dd/MM/yyyy")
        self.start_date_input.setEnabled(False)
        self.end_date_input.setEnabled(False)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItem("Todos", None)
        self.status_combo.addItem("Rascunho", RentalStatus.DRAFT)
        self.status_combo.addItem("Confirmado", RentalStatus.CONFIRMED)
        self.status_combo.addItem("Cancelado", RentalStatus.CANCELED)
        self.status_combo.addItem("Concluído", RentalStatus.COMPLETED)

        self.payment_combo = QtWidgets.QComboBox()
        self.payment_combo.addItem("Todos", None)
        self.payment_combo.addItem("Pendente", PaymentStatus.UNPAID)
        self.payment_combo.addItem("Parcial", PaymentStatus.PARTIAL)
        self.payment_combo.addItem("Pago", PaymentStatus.PAID)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Cliente ou endereço")

        self.clear_filters_button = QtWidgets.QPushButton("Limpar filtros")
        self.clear_filters_button.setMinimumHeight(40)
        self.clear_filters_button.clicked.connect(self._on_clear_filters)

        filters_layout.addWidget(self.date_filter_check, 0, 0)
        filters_layout.addWidget(QtWidgets.QLabel("De"), 0, 1)
        filters_layout.addWidget(self.start_date_input, 0, 2)
        filters_layout.addWidget(QtWidgets.QLabel("Até"), 0, 3)
        filters_layout.addWidget(self.end_date_input, 0, 4)
        filters_layout.addWidget(QtWidgets.QLabel("Status"), 1, 0)
        filters_layout.addWidget(self.status_combo, 1, 1, 1, 2)
        filters_layout.addWidget(QtWidgets.QLabel("Pagamento"), 1, 3)
        filters_layout.addWidget(self.payment_combo, 1, 4)
        filters_layout.addWidget(QtWidgets.QLabel("Busca"), 2, 0)
        filters_layout.addWidget(self.search_input, 2, 1, 1, 3)
        filters_layout.addWidget(self.clear_filters_button, 2, 4)
        filters_layout.setColumnStretch(5, 1)

        layout.addWidget(filters_group)

        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Data", "Cliente", "Endereço", "Status", "Pagamento", "Total", "Pago"]
        )
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        actions_layout = QtWidgets.QHBoxLayout()
        self.details_button = QtWidgets.QPushButton("Ver detalhes")
        self.edit_button = QtWidgets.QPushButton("Editar")
        self.cancel_button = QtWidgets.QPushButton("Cancelar")
        self.complete_button = QtWidgets.QPushButton("Concluir")
        self.payment_button = QtWidgets.QPushButton("Registrar pagamento")
        self.generate_contract_button = QtWidgets.QPushButton("Gerar contrato")
        self.generate_receipt_button = QtWidgets.QPushButton("Gerar recibo")
        self.open_contract_button = QtWidgets.QPushButton("Abrir último contrato")
        self.open_receipt_button = QtWidgets.QPushButton("Abrir último recibo")
        for button in (
            self.details_button,
            self.edit_button,
            self.cancel_button,
            self.complete_button,
            self.payment_button,
            self.generate_contract_button,
            self.generate_receipt_button,
            self.open_contract_button,
            self.open_receipt_button,
        ):
            button.setMinimumHeight(40)

        self.details_button.clicked.connect(self._on_view_details)
        self.edit_button.clicked.connect(self._on_edit)
        self.cancel_button.clicked.connect(self._on_cancel)
        self.complete_button.clicked.connect(self._on_complete)
        self.payment_button.clicked.connect(self._on_payment)
        self.generate_contract_button.clicked.connect(
            lambda: self._on_generate_document(DocumentType.CONTRACT)
        )
        self.generate_receipt_button.clicked.connect(
            lambda: self._on_generate_document(DocumentType.RECEIPT)
        )
        self.open_contract_button.clicked.connect(
            lambda: self._on_open_latest(DocumentType.CONTRACT)
        )
        self.open_receipt_button.clicked.connect(
            lambda: self._on_open_latest(DocumentType.RECEIPT)
        )

        actions_layout.addWidget(self.details_button)
        actions_layout.addWidget(self.edit_button)
        actions_layout.addWidget(self.cancel_button)
        actions_layout.addWidget(self.complete_button)
        actions_layout.addWidget(self.payment_button)
        actions_layout.addWidget(self.generate_contract_button)
        actions_layout.addWidget(self.generate_receipt_button)
        actions_layout.addWidget(self.open_contract_button)
        actions_layout.addWidget(self.open_receipt_button)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        self._set_actions_enabled(False)

        self.date_filter_check.toggled.connect(self._on_filters_changed)
        self.start_date_input.dateChanged.connect(self._on_filters_changed)
        self.end_date_input.dateChanged.connect(self._on_filters_changed)
        self.status_combo.currentIndexChanged.connect(self._on_filters_changed)
        self.payment_combo.currentIndexChanged.connect(self._on_filters_changed)
        self.search_input.textChanged.connect(self._on_filters_changed)
        self.date_filter_check.toggled.connect(self._toggle_date_filter)

        self.setStyleSheet(
            """
            QGroupBox {
                font-weight: 600;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit, QDateEdit, QComboBox {
                font-size: 14px;
                padding: 4px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 14px;
            }
            """
        )

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.details_button.setEnabled(enabled)
        self.edit_button.setEnabled(enabled)
        self.cancel_button.setEnabled(enabled)
        self.complete_button.setEnabled(enabled)
        self.payment_button.setEnabled(enabled)
        self.generate_contract_button.setEnabled(enabled)
        self.generate_receipt_button.setEnabled(enabled)
        if not enabled:
            self._set_open_button_state(
                self.open_contract_button,
                False,
                "Selecione um aluguel para abrir o contrato.",
            )
            self._set_open_button_state(
                self.open_receipt_button,
                False,
                "Selecione um aluguel para abrir o recibo.",
            )

    def _on_filters_changed(self) -> None:
        self._filter_timer.start()

    def refresh(self) -> None:
        self._load_rentals()

    def _toggle_date_filter(self, checked: bool) -> None:
        self.start_date_input.setEnabled(checked)
        self.end_date_input.setEnabled(checked)
        if checked:
            self._normalize_filter_dates()

    def _on_clear_filters(self) -> None:
        self.date_filter_check.setChecked(False)
        today = QtCore.QDate.currentDate()
        self.start_date_input.setDate(today)
        self.end_date_input.setDate(today)
        self.status_combo.setCurrentIndex(0)
        self.payment_combo.setCurrentIndex(0)
        self.search_input.clear()
        self._load_rentals()

    def _normalize_filter_dates(self) -> None:
        if self.start_date_input.date() > self.end_date_input.date():
            self.end_date_input.setDate(self.start_date_input.date())

    def _load_rentals(self) -> None:
        try:
            customers = self._services.customer_repo.list_all()
            self._customers_map = {
                customer.id or 0: customer.name for customer in customers
            }
            start_date = None
            end_date = None
            if self.date_filter_check.isChecked():
                self._normalize_filter_dates()
                start_date = self.start_date_input.date().toString("yyyy-MM-dd")
                end_date = self.end_date_input.date().toString("yyyy-MM-dd")
            status = self.status_combo.currentData()
            payment_status = self.payment_combo.currentData()
            search = self.search_input.text().strip() or None
            rentals = rental_repo.list_rentals(
                start_date=start_date,
                end_date=end_date,
                status=status,
                payment_status=payment_status,
                search=search,
                connection=self._services.connection,
            )
            today = QtCore.QDate.currentDate().toString("yyyy-MM-dd")
            rentals_today = rental_repo.list_rentals(
                start_date=today,
                end_date=today,
                connection=self._services.connection,
            )
        except Exception:
            _show_error(self, "Não foi possível carregar a agenda de aluguéis.")
            return
        self._rentals = rentals
        self._render_table()
        self._render_today_summary(rentals_today)

    def _render_today_summary(self, rentals_today: List[Rental]) -> None:
        count = len(rentals_today)
        if count == 0:
            self.today_banner.set_subtitle("Nenhum aluguel previsto para hoje.")
            self.today_banner.set_content("Assim que houver um aluguel, ele aparece aqui.")
            return
        label = "aluguel" if count == 1 else "aluguéis"
        self.today_banner.set_subtitle(f"{count} {label} para hoje.")
        items = []
        for rental in rentals_today[:5]:
            customer_name = self._customers_map.get(rental.customer_id, "—")
            items.append(
                f"{html.escape(customer_name)} — "
                f"{html.escape(_status_label(rental.status))} — "
                f"{html.escape(_format_currency(rental.total_value))}"
            )
        if count > 5:
            items.append(f"… e mais {count - 5} {label}.")
        list_markup = "<ul style=\"margin: 0; padding-left: 18px;\">"
        list_markup += "".join(f"<li>{item}</li>" for item in items)
        list_markup += "</ul>"
        self.today_banner.set_content(list_markup)

    def _render_table(self) -> None:
        self.table.setRowCount(len(self._rentals))
        for row, rental in enumerate(self._rentals):
            customer_name = self._customers_map.get(rental.customer_id, "—")
            self.table.setItem(
                row, 0, QtWidgets.QTableWidgetItem(_format_date(rental.event_date))
            )
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(customer_name))
            self.table.setItem(
                row,
                2,
                QtWidgets.QTableWidgetItem(_summarize_address(rental.address)),
            )
            self.table.setItem(
                row, 3, QtWidgets.QTableWidgetItem(_status_label(rental.status))
            )
            self.table.setItem(
                row,
                4,
                QtWidgets.QTableWidgetItem(_payment_label(rental.payment_status)),
            )
            self.table.setItem(
                row, 5, QtWidgets.QTableWidgetItem(_format_currency(rental.total_value))
            )
            self.table.setItem(
                row, 6, QtWidgets.QTableWidgetItem(_format_currency(rental.paid_value))
            )
        self.table.setSortingEnabled(False)
        self.table.resizeRowsToContents()
        self._on_selection_changed()

    def _get_selected_rental(self) -> Optional[Rental]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self._rentals):
            return None
        return self._rentals[row]

    def _on_selection_changed(self) -> None:
        rental = self._get_selected_rental()
        has_selection = rental is not None
        self._set_actions_enabled(has_selection)
        if rental and rental.id:
            self._update_document_buttons(rental.id)

    def _on_view_details(self) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        dialog = RentalDetailsDialog(self._services, rental_id=rental.id)
        dialog.exec()

    def _on_edit(self) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        dialog = RentalEditDialog(self._services, rental_id=rental.id)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        self._load_rentals()

    def _on_cancel(self) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        if not _confirm_action(
            self, "Tem certeza que deseja cancelar este aluguel?"
        ):
            return
        try:
            self._services.rental_service.cancel_rental(rental.id)
        except Exception:
            _show_error(self, "Não foi possível cancelar o aluguel. Tente novamente.")
            return
        self._services.data_bus.data_changed.emit()
        self._load_rentals()

    def _on_complete(self) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        if not _confirm_action(self, "Confirmar conclusão deste aluguel?"):
            return
        try:
            self._services.rental_service.complete_rental(rental.id)
        except Exception:
            _show_error(self, "Não foi possível concluir o aluguel. Tente novamente.")
            return
        self._services.data_bus.data_changed.emit()
        self._load_rentals()

    def _on_payment(self) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        dialog = PaymentEntryDialog("Registrar pagamento")
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_payment_data()
        try:
            self._services.payment_service.add_payment(
                rental_id=rental.id,
                amount=float(data["amount"]),
                method=data["method"],
                paid_at=data["paid_at"],
                note=data["note"],
            )
        except Exception:
            _show_error(self, "Não foi possível registrar o pagamento. Tente novamente.")
            return
        self._services.data_bus.data_changed.emit()
        self._load_rentals()

    def _set_open_button_state(
        self, button: QtWidgets.QPushButton, enabled: bool, tooltip: str
    ) -> None:
        button.setEnabled(enabled)
        button.setToolTip(tooltip)

    def _update_document_buttons(self, rental_id: int) -> None:
        for doc_type in (DocumentType.CONTRACT, DocumentType.RECEIPT):
            document = self._services.document_repo.get_latest(rental_id, doc_type)
            self._latest_documents[doc_type] = document
        self._apply_document_state(DocumentType.CONTRACT, self.open_contract_button)
        self._apply_document_state(DocumentType.RECEIPT, self.open_receipt_button)

    def _apply_document_state(
        self, doc_type: DocumentType, button: QtWidgets.QPushButton
    ) -> None:
        document = self._latest_documents.get(doc_type)
        label = "contrato" if doc_type == DocumentType.CONTRACT else "recibo"
        if not document:
            self._set_open_button_state(
                button,
                False,
                f"Nenhum {label} gerado para este aluguel.",
            )
            return
        path = Path(document.file_path)
        if not path.exists():
            self._set_open_button_state(
                button,
                False,
                f"Arquivo do {label} não encontrado. Gere novamente.",
            )
            return
        self._set_open_button_state(button, True, f"Abrir último {label} gerado.")

    def _on_generate_document(self, doc_type: DocumentType) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        try:
            rental_payload = self._build_pdf_payload(rental.id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = (
                get_pdfs_dir()
                / f"aluguel_{rental.id}_{timestamp}_{doc_type.value}.pdf"
            )
            generate_rental_pdf(
                rental_payload,
                output_path,
                kind=doc_type.value,
            )
            checksum = self._calculate_checksum(output_path)
            generated_at = datetime.now().isoformat(timespec="seconds")
            self._services.document_repo.upsert(
                rental_id=rental.id,
                doc_type=doc_type,
                file_path=str(output_path),
                generated_at=generated_at,
                checksum=checksum,
            )
            self._update_document_buttons(rental.id)
        except Exception:
            _show_error(self, "Não foi possível gerar o PDF. Tente novamente.")
            return

        message = QtWidgets.QMessageBox(self)
        message.setWindowTitle("PDF gerado")
        message.setText(
            "PDF gerado com sucesso. Deseja abrir o arquivo ou a pasta de destino?"
        )
        open_file_button = message.addButton("Abrir PDF", QtWidgets.QMessageBox.AcceptRole)
        open_folder_button = message.addButton(
            "Abrir pasta", QtWidgets.QMessageBox.AcceptRole
        )
        message.addButton("Fechar", QtWidgets.QMessageBox.RejectRole)
        message.exec()

        clicked = message.clickedButton()
        if clicked == open_file_button:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl.fromLocalFile(str(output_path))
            )
        elif clicked == open_folder_button:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl.fromLocalFile(str(output_path.parent))
            )

    def _on_open_latest(self, doc_type: DocumentType) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        document = self._latest_documents.get(doc_type)
        if not document:
            return
        path = Path(document.file_path)
        if not path.exists():
            _show_error(
                self,
                "Arquivo não encontrado. Gere o documento novamente para atualizar.",
            )
            self._update_document_buttons(rental.id)
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _build_pdf_payload(
        self, rental_id: int
    ) -> tuple[Rental, list[SimpleNamespace], Customer]:
        rental_data = rental_repo.get_rental_with_items(
            rental_id,
            connection=self._services.connection,
        )
        if not rental_data:
            raise RuntimeError("Aluguel não encontrado.")
        rental, items = rental_data
        customer = self._services.customer_repo.get_by_id(rental.customer_id)
        if not customer:
            customer = Customer(
                id=None,
                name="Cliente não encontrado",
                phone=None,
                notes=None,
            )
        products = self._services.product_repo.list_all()
        product_map = {product.id: product for product in products}
        items_for_pdf = []
        for item in items:
            product = product_map.get(item.product_id)
            items_for_pdf.append(
                SimpleNamespace(
                    product_id=item.product_id,
                    product_name=product.name if product else f"Produto {item.product_id}",
                    qty=item.qty,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
            )
        return rental, items_for_pdf, customer

    def _calculate_checksum(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()
