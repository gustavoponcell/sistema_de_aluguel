"""Screen for creating a new rental."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from rental_manager.domain.models import Customer, Product
from rental_manager.services.errors import ValidationError
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.ui.screens.customers_screen import CustomerDialog


@dataclass
class RentalItemDraft:
    """Item draft used in the new rental screen."""

    product_id: int
    product_name: str
    qty: int
    unit_price: float

    @property
    def line_total(self) -> float:
        return self.qty * self.unit_price


class NewRentalScreen(BaseScreen):
    """Screen for creating a new rental workflow."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._customers: List[Customer] = []
        self._products: List[Product] = []
        self._items: List[RentalItemDraft] = []
        self._editing_index: Optional[int] = None
        self._build_ui()
        self._load_customers()
        self._load_products()

    def refresh(self) -> None:
        self._load_customers()
        self._load_products()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QtWidgets.QLabel("Novo Aluguel")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Inicie um novo aluguel com dados do cliente, datas e itens."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #555; font-size: 14px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QtWidgets.QFormLayout()
        form.setVerticalSpacing(14)
        customer_row = QtWidgets.QHBoxLayout()
        self.customer_combo = QtWidgets.QComboBox()
        self.customer_combo.setMinimumWidth(240)
        self.customer_combo.setMinimumHeight(36)
        self.new_customer_button = QtWidgets.QPushButton("Novo Cliente")
        self.new_customer_button.setMinimumHeight(40)
        self.new_customer_button.clicked.connect(self._on_new_customer)
        customer_row.addWidget(self.customer_combo)
        customer_row.addWidget(self.new_customer_button)
        customer_row.addStretch()

        self.event_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.event_date_input.setCalendarPopup(True)
        self.event_date_input.setDisplayFormat("dd/MM/yyyy")
        self.start_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("dd/MM/yyyy")
        self.end_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDisplayFormat("dd/MM/yyyy")
        self.start_date_input.dateChanged.connect(self._sync_end_date_min)
        self._sync_end_date_min(self.start_date_input.date())

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
        self.product_combo.currentIndexChanged.connect(
            self._on_product_selected
        )
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

        button_layout = QtWidgets.QHBoxLayout()
        self.save_draft_button = QtWidgets.QPushButton("Salvar como rascunho")
        self.confirm_button = QtWidgets.QPushButton("Confirmar aluguel")
        self.save_draft_button.setMinimumHeight(44)
        self.confirm_button.setMinimumHeight(44)
        self.save_draft_button.clicked.connect(self._on_save_draft)
        self.confirm_button.clicked.connect(self._on_confirm_rental)
        button_layout.addWidget(self.save_draft_button)
        button_layout.addWidget(self.confirm_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()

        self.setStyleSheet(
            """
            QGroupBox {
                font-weight: 600;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
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
            """
        )

    def _show_warning(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "Atenção", message)

    def _show_error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "Erro", message)

    def _show_success(self, message: str) -> None:
        QtWidgets.QMessageBox.information(self, "Sucesso", message)

    def _confirm_action(self, message: str) -> bool:
        response = QtWidgets.QMessageBox.question(
            self,
            "Confirmação",
            message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        return response == QtWidgets.QMessageBox.Yes

    def _sync_end_date_min(self, new_start_date: QtCore.QDate) -> None:
        minimum_end_date = new_start_date.addDays(1)
        self.end_date_input.setMinimumDate(minimum_end_date)
        if self.end_date_input.date() < minimum_end_date:
            self.end_date_input.setDate(minimum_end_date)

    def _load_customers(self) -> None:
        try:
            customers = self._services.customer_repo.list_all()
        except Exception:
            self._show_error("Não foi possível carregar os clientes.")
            return
        self._customers = customers
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("Selecione um cliente", None)
        for customer in customers:
            self.customer_combo.addItem(customer.name, customer.id)
        self.customer_combo.blockSignals(False)

    def _load_products(self) -> None:
        try:
            products = self._services.product_repo.list_active()
        except Exception:
            self._show_error("Não foi possível carregar os produtos.")
            return
        self._products = products
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self.product_combo.addItem("Selecione um produto", None)
        for product in products:
            self.product_combo.addItem(product.name, product.id)
        self.product_combo.blockSignals(False)
        self._apply_selected_product_price()

    def _on_product_selected(self) -> None:
        self._apply_selected_product_price()

    def _apply_selected_product_price(self) -> None:
        product = self._get_selected_product()
        if not product or product.unit_price is None:
            self.unit_price_input.setValue(0.0)
            return
        self.unit_price_input.setValue(float(product.unit_price))

    def _get_selected_product(self) -> Optional[Product]:
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

    def _on_new_customer(self) -> None:
        dialog = CustomerDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            customer = self._services.customer_repo.create(
                name=data["name"] or "",
                phone=data["phone"],
                notes=data["notes"],
            )
        except Exception:
            self._show_error(
                "Não foi possível salvar o cliente. Verifique os dados e tente novamente."
            )
            return
        self._services.data_bus.data_changed.emit()
        self._load_customers()
        if customer and customer.id:
            index = self.customer_combo.findData(customer.id)
            if index >= 0:
                self.customer_combo.setCurrentIndex(index)

    def _on_add_item(self) -> None:
        if not self._validate_dates():
            return
        product = self._get_selected_product()
        if not product or product.id is None:
            self._show_warning("Selecione um produto para adicionar.")
            return
        qty = int(self.qty_input.value())
        unit_price = float(self.unit_price_input.value())
        if qty <= 0:
            self._show_warning("Informe uma quantidade maior que zero.")
            return
        if unit_price <= 0:
            self._show_warning("Informe um preço unitário válido.")
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
                row,
                2,
                QtWidgets.QTableWidgetItem(self._format_currency(item.unit_price)),
            )
            self.items_table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(self._format_currency(item.line_total)),
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
        self.total_label.setText(f"Total: {self._format_currency(total)}")

    def _format_currency(self, value: float) -> str:
        formatted = f"{value:,.2f}"
        return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"

    def _get_dates(self) -> tuple[date, date, date]:
        event_date = self.event_date_input.date().toPython()
        start_date = self.start_date_input.date().toPython()
        end_date = self.end_date_input.date().toPython()
        return event_date, start_date, end_date

    def _validate_dates(self) -> bool:
        _event_date, start_date, end_date = self._get_dates()
        if start_date >= end_date:
            self._show_warning(
                "A data de término deve ser posterior à data de início."
            )
            return False
        return True

    def _validate_form(self) -> bool:
        if not self._get_selected_customer_id():
            self._show_warning("Selecione um cliente para o aluguel.")
            return False
        if not self._validate_dates():
            return False
        if not self._items:
            self._show_warning("Adicione ao menos um item ao aluguel.")
            return False
        return True

    def _validate_inventory(self, items: List[RentalItemDraft]) -> bool:
        _event_date, start_date, end_date = self._get_dates()
        aggregated = self._aggregate_items(items)
        try:
            self._services.inventory_service.validate_request(
                aggregated,
                start_date.isoformat(),
                end_date.isoformat(),
            )
        except ValueError as exc:
            self._show_warning(str(exc))
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

    def _save_rental(self, confirm: bool) -> bool:
        if not self._validate_form():
            return False
        if not self._validate_inventory(self._items):
            return False
        customer_id = self._get_selected_customer_id()
        if customer_id is None:
            return False
        event_date, start_date, end_date = self._get_dates()
        items_payload = self._build_items_payload()
        total_value = sum(item.line_total for item in self._items)
        if total_value <= 0 and not self._confirm_action(
            "O total do aluguel está R$ 0,00. Deseja continuar mesmo assim?"
        ):
            return False
        try:
            rental = self._services.rental_service.create_draft_rental(
                customer_id=customer_id,
                event_date=event_date.isoformat(),
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                address=self.address_input.toPlainText().strip() or None,
                items=items_payload,
                total_value=total_value,
            )
            if confirm and rental.id:
                self._services.rental_service.confirm_rental(rental.id)
        except ValidationError as exc:
            self._show_warning(str(exc))
            return False
        except Exception:
            self._show_error(
                "Não foi possível salvar o aluguel. Verifique os dados e tente novamente."
            )
            return False
        self._services.data_bus.data_changed.emit()
        return True

    def _on_save_draft(self) -> None:
        if not self._save_rental(confirm=False):
            return
        self._show_success("Aluguel salvo como rascunho.")
        self._clear_form()

    def _on_confirm_rental(self) -> None:
        if not self._save_rental(confirm=True):
            return
        self._show_success("Aluguel confirmado com sucesso.")
        self._clear_form()

    def _clear_form(self) -> None:
        self.customer_combo.setCurrentIndex(0)
        today = QtCore.QDate.currentDate()
        self.event_date_input.setDate(today)
        self.start_date_input.setDate(today)
        self.end_date_input.setDate(today.addDays(1))
        self._sync_end_date_min(today)
        self.address_input.clear()
        self.product_combo.setCurrentIndex(0)
        self.qty_input.setValue(1)
        self.unit_price_input.setValue(0.0)
        self._items = []
        self._editing_index = None
        self.add_item_button.setText("Adicionar item")
        self._render_items_table()
        self._update_total_label()
