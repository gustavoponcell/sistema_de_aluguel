"""Screen for rentals agenda."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.domain.models import (
    Customer,
    PaymentStatus,
    Rental,
    RentalItem,
    RentalStatus,
)
from rental_manager.paths import get_pdfs_dir
from rental_manager.repositories import rental_repo
from rental_manager.services.errors import ValidationError
from rental_manager.ui.app_services import AppServices
from rental_manager.utils.pdf_generator import generate_rental_pdf


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_date(value: str) -> str:
    parsed = QtCore.QDate.fromString(value, "yyyy-MM-dd")
    return parsed.toString("dd/MM/yyyy") if parsed.isValid() else value


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
        PaymentStatus.UNPAID: "Não pago",
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
        info_layout.addRow(
            "Pagamento:", QtWidgets.QLabel(_payment_label(self._rental.payment_status))
        )
        info_layout.addRow(
            "Total:", QtWidgets.QLabel(_format_currency(self._rental.total_value))
        )
        info_layout.addRow(
            "Pago:", QtWidgets.QLabel(_format_currency(self._rental.paid_value))
        )
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

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class PaymentDialog(QtWidgets.QDialog):
    """Dialog to register payment for a rental."""

    def __init__(self, total_value: float, paid_value: float) -> None:
        super().__init__()
        self._total_value = total_value
        self._paid_value = paid_value
        self.setWindowTitle("Registrar pagamento")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        summary = QtWidgets.QLabel(
            f"Total do aluguel: {_format_currency(self._total_value)}"
        )
        layout.addWidget(summary)

        form = QtWidgets.QFormLayout()
        self.value_input = QtWidgets.QDoubleSpinBox()
        self.value_input.setRange(0.0, max(self._total_value, 0.0))
        self.value_input.setDecimals(2)
        self.value_input.setPrefix("R$ ")
        self.value_input.setValue(self._paid_value)
        self.full_paid_check = QtWidgets.QCheckBox("Marcar como pago total")
        self.full_paid_check.setChecked(self._paid_value >= self._total_value)
        self.full_paid_check.toggled.connect(self._on_toggle_full_payment)

        form.addRow("Valor pago:", self.value_input)
        form.addRow("", self.full_paid_check)
        layout.addLayout(form)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._on_toggle_full_payment(self.full_paid_check.isChecked())

    def _on_toggle_full_payment(self, checked: bool) -> None:
        if checked:
            self.value_input.setValue(self._total_value)
        self.value_input.setEnabled(not checked)

    def _on_accept(self) -> None:
        if self.value_input.value() < 0:
            _show_warning(self, "Informe um valor pago válido.")
            return
        self.accept()

    def get_paid_value(self) -> float:
        return float(self.value_input.value())


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
        self.end_date_input.setMinimumDate(new_start_date)
        if self.end_date_input.date() < new_start_date:
            self.end_date_input.setDate(new_start_date)

    def _validate_dates(self) -> bool:
        _event_date, start_date, end_date = self._get_dates()
        if start_date > end_date:
            _show_warning(
                self, "A data de término não pode ser anterior à data de início."
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
                paid_value=self._rental.paid_value,
                status=self._rental.status,
            )
        except ValidationError as exc:
            _show_warning(self, str(exc))
            return
        except Exception:
            _show_error(self, "Não foi possível atualizar o aluguel. Tente novamente.")
            return
        self.accept()


class RentalsScreen(QtWidgets.QWidget):
    """Screen for the rentals agenda."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._rentals: List[Rental] = []
        self._customers_map: dict[int, str] = {}
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

        self.today_frame = QtWidgets.QFrame()
        self.today_frame.setObjectName("todayFrame")
        today_layout = QtWidgets.QVBoxLayout(self.today_frame)
        today_layout.setContentsMargins(16, 12, 16, 12)
        today_layout.setSpacing(8)
        today_title = QtWidgets.QLabel("Aluguéis de hoje")
        today_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.today_summary_label = QtWidgets.QLabel()
        self.today_summary_label.setStyleSheet("font-size: 14px;")
        self.today_list_label = QtWidgets.QLabel()
        self.today_list_label.setWordWrap(True)
        self.today_list_label.setStyleSheet("font-size: 14px; color: #333;")
        today_layout.addWidget(today_title)
        today_layout.addWidget(self.today_summary_label)
        today_layout.addWidget(self.today_list_label)
        layout.addWidget(self.today_frame)

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
        self.payment_combo.addItem("Não pago", PaymentStatus.UNPAID)
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
        self.pdf_button = QtWidgets.QPushButton("Gerar PDF")
        for button in (
            self.details_button,
            self.edit_button,
            self.cancel_button,
            self.complete_button,
            self.payment_button,
            self.pdf_button,
        ):
            button.setMinimumHeight(40)

        self.details_button.clicked.connect(self._on_view_details)
        self.edit_button.clicked.connect(self._on_edit)
        self.cancel_button.clicked.connect(self._on_cancel)
        self.complete_button.clicked.connect(self._on_complete)
        self.payment_button.clicked.connect(self._on_payment)
        self.pdf_button.clicked.connect(self._on_pdf)

        actions_layout.addWidget(self.details_button)
        actions_layout.addWidget(self.edit_button)
        actions_layout.addWidget(self.cancel_button)
        actions_layout.addWidget(self.complete_button)
        actions_layout.addWidget(self.payment_button)
        actions_layout.addWidget(self.pdf_button)
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
            QFrame#todayFrame {
                background-color: #fff6db;
                border: 1px solid #f3d48a;
                border-radius: 10px;
            }
            """
        )

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.details_button.setEnabled(enabled)
        self.edit_button.setEnabled(enabled)
        self.cancel_button.setEnabled(enabled)
        self.complete_button.setEnabled(enabled)
        self.payment_button.setEnabled(enabled)
        self.pdf_button.setEnabled(enabled)

    def _on_filters_changed(self) -> None:
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
            self.today_summary_label.setText("Nenhum aluguel previsto para hoje.")
            self.today_list_label.setText("Assim que houver um aluguel, ele aparece aqui.")
            return
        label = "aluguel" if count == 1 else "aluguéis"
        self.today_summary_label.setText(f"{count} {label} para hoje.")
        lines = []
        for rental in rentals_today[:5]:
            customer_name = self._customers_map.get(rental.customer_id, "—")
            lines.append(
                f"• {customer_name} — {_status_label(rental.status)} — "
                f"{_format_currency(rental.total_value)}"
            )
        if count > 5:
            lines.append(f"… e mais {count - 5} {label}.")
        self.today_list_label.setText("\n".join(lines))

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
        has_selection = self._get_selected_rental() is not None
        self._set_actions_enabled(has_selection)

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
        self._load_rentals()

    def _on_payment(self) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        dialog = PaymentDialog(rental.total_value, rental.paid_value)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            self._services.rental_service.set_payment(
                rental_id=rental.id,
                paid_value=dialog.get_paid_value(),
            )
        except Exception:
            _show_error(self, "Não foi possível registrar o pagamento. Tente novamente.")
            return
        self._load_rentals()

    def _on_pdf(self) -> None:
        rental = self._get_selected_rental()
        if not rental or not rental.id:
            return
        choice, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Gerar PDF",
            "Selecione o tipo de documento:",
            ["Contrato", "Recibo"],
            0,
            False,
        )
        if not ok:
            return
        kind = "contract" if choice == "Contrato" else "receipt"
        try:
            rental_data = rental_repo.get_rental_with_items(
                rental.id,
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = (
                get_pdfs_dir() / f"aluguel_{rental.id}_{timestamp}_{kind}.pdf"
            )
            generate_rental_pdf(
                (rental, items_for_pdf, customer),
                output_path,
                kind=kind,
            )
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
