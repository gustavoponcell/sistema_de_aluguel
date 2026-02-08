"""Screen for creating a new rental."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from rental_manager.domain.models import Customer, Product, ProductKind
from rental_manager.services.errors import ValidationError
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.ui.screens.customers_screen import CustomerDialog
from rental_manager.ui.strings import (
    TERM_ITEM,
    TERM_ORDER,
    TITLE_CONFIRMATION,
    TITLE_ERROR,
    TITLE_SUCCESS,
    TITLE_WARNING,
    product_kind_label,
)
from rental_manager.utils.theme import apply_table_theme


@dataclass
class RentalItemDraft:
    """Item draft used in the new rental screen."""

    product_id: int
    product_name: str
    product_kind: ProductKind
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
        self._building_ui = True
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QtWidgets.QLabel(f"Novo {TERM_ORDER}")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Inicie um novo pedido com dados do cliente, datas e itens."
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

        self.phone_input = QtWidgets.QLineEdit()
        self.phone_input.setPlaceholderText("Opcional")

        self.event_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.event_date_input.setCalendarPopup(True)
        self.event_date_input.setDisplayFormat("dd/MM/yyyy")
        self.start_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("dd/MM/yyyy")
        self.end_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDisplayFormat("dd/MM/yyyy")
        self.event_date_label = QtWidgets.QLabel("Data do pedido")
        self.start_date_label = QtWidgets.QLabel("Início")
        self.end_date_label = QtWidgets.QLabel("Fim")
        self.duration_label = QtWidgets.QLabel("")
        self.duration_label.setStyleSheet("color: #666; font-size: 13px;")
        self._sync_end_date_min(self.start_date_input.date())
        self._update_duration_label()
        self.start_date_input.dateChanged.connect(self._sync_end_date_min)
        self.start_date_input.dateChanged.connect(self._on_dates_changed)
        self.end_date_input.dateChanged.connect(self._on_dates_changed)

        dates_row = QtWidgets.QHBoxLayout()
        dates_row.addWidget(self.event_date_label)
        dates_row.addWidget(self.event_date_input)
        dates_row.addSpacing(12)
        dates_row.addWidget(self.start_date_label)
        dates_row.addWidget(self.start_date_input)
        dates_row.addSpacing(12)
        dates_row.addWidget(self.end_date_label)
        dates_row.addWidget(self.end_date_input)
        dates_row.addSpacing(12)
        dates_row.addWidget(self.duration_label)
        dates_row.addStretch()

        self.delivery_checkbox = QtWidgets.QCheckBox("Entrega?")
        self.delivery_checkbox.stateChanged.connect(self._on_delivery_changed)
        self.delivery_hint = QtWidgets.QLabel("Retirada pelo cliente")
        self.delivery_hint.setStyleSheet("color: #666; font-size: 13px;")

        self.address_input = QtWidgets.QPlainTextEdit()
        self.address_input.setFixedHeight(80)
        self.address_input.setPlaceholderText("Rua, número, bairro, referência")

        form.addRow("Cliente:", customer_row)
        form.addRow("Telefone:", self.phone_input)
        form.addRow("Datas:", dates_row)
        form.addRow("", self.delivery_checkbox)
        form.addRow("", self.delivery_hint)
        form.addRow("Endereço:", self.address_input)

        layout.addLayout(form)

        items_group = QtWidgets.QGroupBox("Itens do pedido")
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

        item_form.addWidget(QtWidgets.QLabel(TERM_ITEM), 0, 0)
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
            [TERM_ITEM, "Quantidade", "Preço unitário", "Total", "Ações"]
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
        apply_table_theme(
            self.items_table,
            "dark" if self._services.theme_manager.is_dark() else "light",
        )
        self._services.theme_manager.theme_changed.connect(
            lambda theme, table=self.items_table: apply_table_theme(table, theme)
        )

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
        self.confirm_button = QtWidgets.QPushButton("Confirmar pedido")
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
        self._apply_delivery_state()
        self._toggle_rental_dates()
        self._building_ui = False

    def _show_warning(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, TITLE_WARNING, message)

    def _show_error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, TITLE_ERROR, message)

    def _show_success(self, message: str) -> None:
        QtWidgets.QMessageBox.information(self, TITLE_SUCCESS, message)

    def _on_delivery_changed(self) -> None:
        self._apply_delivery_state()

    def _apply_delivery_state(self) -> None:
        delivery_required = self.delivery_checkbox.isChecked()
        self.address_input.setEnabled(delivery_required)
        self.delivery_hint.setVisible(not delivery_required)
        if not delivery_required:
            self.address_input.clear()

    def _toggle_rental_dates(self) -> None:
        has_rental_items = any(
            item.product_kind == ProductKind.RENTAL for item in self._items
        )
        self.start_date_label.setVisible(has_rental_items)
        self.start_date_input.setVisible(has_rental_items)
        self.end_date_label.setVisible(has_rental_items)
        self.end_date_input.setVisible(has_rental_items)
        self.duration_label.setVisible(has_rental_items)
        if has_rental_items:
            self._sync_end_date_min(self.start_date_input.date())

    def _confirm_action(self, message: str) -> bool:
        response = QtWidgets.QMessageBox.question(
            self,
            TITLE_CONFIRMATION,
            message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        return response == QtWidgets.QMessageBox.Yes

    def _sync_end_date_min(self, new_start_date: QtCore.QDate) -> None:
        minimum_end_date = new_start_date.addDays(1)
        self.end_date_input.setMinimumDate(minimum_end_date)
        if self.end_date_input.date() < minimum_end_date:
            self.end_date_input.setDate(minimum_end_date)
        self._update_duration_label()

    def _on_dates_changed(self) -> None:
        if getattr(self, "_building_ui", False):
            return
        if not self._requires_rental_dates():
            return
        self._ensure_end_date_after_start()
        self._update_duration_label()
        if not self._items:
            return
        if not self._validate_dates():
            return
        self._validate_inventory(self._items)

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
            self._show_error("Não foi possível carregar os itens.")
            return
        self._products = products
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self.product_combo.addItem("Selecione um item", None)
        for product in products:
            self.product_combo.addItem(self._format_product_label(product), product.id)
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

    def _format_product_label(self, product: Product) -> str:
        kind_label = product_kind_label(product.kind)
        return f"{product.name} • {kind_label}"

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
        product = self._get_selected_product()
        if not product or product.id is None:
            self._show_warning("Selecione um item para adicionar.")
            return
        if not self._validate_dates(selected_kind=product.kind):
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
            product_kind=product.kind,
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
        self._toggle_rental_dates()

    def _prepare_updated_items(
        self,
        product_id: int,
        product_name: str,
        product_kind: ProductKind,
        qty: int,
        unit_price: float,
    ) -> List[RentalItemDraft]:
        items = list(self._items)
        if self._editing_index is None:
            for item in items:
                if item.product_id == product_id:
                    item.qty += qty
                    item.unit_price = unit_price
                    return items
            items.append(
                RentalItemDraft(product_id, product_name, product_kind, qty, unit_price)
            )
            return items
        if self._editing_index < 0 or self._editing_index >= len(items):
            items.append(
                RentalItemDraft(product_id, product_name, product_kind, qty, unit_price)
            )
            return items
        existing = items[self._editing_index]
        existing.product_id = product_id
        existing.product_name = product_name
        existing.product_kind = product_kind
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
        self._toggle_rental_dates()

    def _update_total_label(self) -> None:
        total = sum(item.line_total for item in self._items)
        self.total_label.setText(f"Total: {self._format_currency(total)}")

    def _format_currency(self, value: float) -> str:
        formatted = f"{value:,.2f}"
        return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"

    def _get_dates(self) -> tuple[date, Optional[date], Optional[date]]:
        event_date = self.event_date_input.date().toPython()
        if self._requires_rental_dates():
            start_date = self.start_date_input.date().toPython()
            end_date = self.end_date_input.date().toPython()
            return event_date, start_date, end_date
        return event_date, None, None

    def _ensure_end_date_after_start(self) -> None:
        start_date = self.start_date_input.date()
        end_date = self.end_date_input.date()
        if end_date <= start_date:
            self.end_date_input.setDate(start_date.addDays(1))

    def _update_duration_label(self) -> None:
        if not hasattr(self, "duration_label"):
            return
        if not self._requires_rental_dates():
            self.duration_label.setText("")
            return
        start_date = self.start_date_input.date()
        end_date = self.end_date_input.date()
        duration_days = max(1, start_date.daysTo(end_date))
        label = "dia" if duration_days == 1 else "dias"
        self.duration_label.setText(f"Duração: {duration_days} {label}")

    def _requires_rental_dates(self, selected_kind: Optional[ProductKind] = None) -> bool:
        if selected_kind == ProductKind.RENTAL:
            return True
        return any(item.product_kind == ProductKind.RENTAL for item in self._items)

    def _validate_dates(self, selected_kind: Optional[ProductKind] = None) -> bool:
        if not self._requires_rental_dates(selected_kind):
            return True
        start_date = self.start_date_input.date().toPython()
        end_date = self.end_date_input.date().toPython()
        if start_date >= end_date:
            self._show_warning(
                "A data de término deve ser posterior à data de início."
            )
            return False
        return True

    def _validate_form(self) -> bool:
        if not self._get_selected_customer_id():
            self._show_warning("Selecione um cliente para o pedido.")
            return False
        if not self._validate_dates():
            return False
        if self.delivery_checkbox.isChecked() and not self.address_input.toPlainText().strip():
            self._show_warning("Informe o endereço de entrega.")
            return False
        if not self._items:
            self._show_warning("Adicione ao menos um item ao pedido.")
            return False
        return True

    def _validate_inventory(self, items: List[RentalItemDraft]) -> bool:
        try:
            requires_rental = any(
                item.product_kind == ProductKind.RENTAL for item in items
            )
            start_date = (
                self.start_date_input.date().toPython() if requires_rental else None
            )
            end_date = self.end_date_input.date().toPython() if requires_rental else None
            self._services.order_service.validate_availability(
                self._build_items_payload(items),
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None,
            )
        except ValueError as exc:
            self._show_warning(str(exc))
            return False
        except ValidationError as exc:
            self._show_warning(str(exc))
            return False
        return True

    def _build_items_payload(
        self, items: Optional[List[RentalItemDraft]] = None
    ) -> List[dict[str, object]]:
        source_items = items if items is not None else self._items
        return [
            {
                "product_id": item.product_id,
                "qty": item.qty,
                "unit_price": item.unit_price,
            }
            for item in source_items
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
            "O total do pedido está R$ 0,00. Deseja continuar mesmo assim?"
        ):
            return False
        try:
            rental = self._services.rental_service.create_draft_rental(
                customer_id=customer_id,
                event_date=event_date.isoformat(),
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None,
                address=self.address_input.toPlainText().strip() or None,
                contact_phone=self.phone_input.text().strip() or None,
                delivery_required=self.delivery_checkbox.isChecked(),
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
                "Não foi possível salvar o pedido. Verifique os dados e tente novamente."
            )
            return False
        self._services.data_bus.data_changed.emit()
        return True

    def _on_save_draft(self) -> None:
        if not self._save_rental(confirm=False):
            return
        self._show_success("Pedido salvo como rascunho.")
        self._clear_form()

    def _on_confirm_rental(self) -> None:
        if not self._save_rental(confirm=True):
            return
        self._show_success("Pedido confirmado com sucesso.")
        self._clear_form()

    def _clear_form(self) -> None:
        self.customer_combo.setCurrentIndex(0)
        self.phone_input.clear()
        today = QtCore.QDate.currentDate()
        self.event_date_input.setDate(today)
        self.start_date_input.setDate(today)
        self.end_date_input.setDate(today.addDays(1))
        self._sync_end_date_min(today)
        self.delivery_checkbox.setChecked(False)
        self.address_input.clear()
        self._apply_delivery_state()
        self.product_combo.setCurrentIndex(0)
        self.qty_input.setValue(1)
        self.unit_price_input.setValue(0.0)
        self._items = []
        self._editing_index = None
        self.add_item_button.setText("Adicionar item")
        self._render_items_table()
        self._update_total_label()
        self._toggle_rental_dates()
