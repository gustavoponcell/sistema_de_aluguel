"""Dialog-based flows for the Assistant screen."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from PySide6 import QtCore, QtWidgets

from rental_manager.domain.models import RentalStatus
from rental_manager.logging_config import get_logger
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.assistant.flow_services import FlowServiceAdapter


def _to_iso(qdate: QtCore.QDate) -> str:
    return qdate.toString("yyyy-MM-dd")


@dataclass(frozen=True)
class FlowDefinition:
    """Metadata to register an assistant flow."""

    code: str
    title: str
    description: str
    dialog_factory: Callable[[AppServices, QtWidgets.QWidget | None], QtWidgets.QDialog]


@dataclass(frozen=True)
class FlowCategory:
    """Grouping for flows."""

    name: str
    flows: Sequence[FlowDefinition]


class BaseFlowDialog(QtWidgets.QDialog):
    """Common layout and feedback helpers."""

    def __init__(
        self,
        services: AppServices,
        title: str,
        subtitle: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._flow = FlowServiceAdapter(services)
        self._logger = get_logger(self.__class__.__name__)
        self.setWindowTitle(title)
        self.resize(640, 480)
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QLabel(subtitle)
        header.setWordWrap(True)
        header.setObjectName("flowSubtitle")
        layout.addWidget(header)
        self._body_layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self._body_layout, stretch=1)
        self._status_label = QtWidgets.QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def show_success(self, message: str) -> None:
        self._status_label.setStyleSheet("color: #16a34a; font-weight: 600;")
        self._status_label.setText(message)

    def show_error(self, message: str) -> None:
        self._status_label.setStyleSheet("color: #dc2626; font-weight: 600;")
        self._status_label.setText(message)


class ActionFlowDialog(BaseFlowDialog):
    """Dialog with form layout and confirm/cancel buttons."""

    def __init__(
        self,
        services: AppServices,
        title: str,
        subtitle: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(services, title, subtitle, parent)
        self._form_layout = QtWidgets.QFormLayout()
        self._form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._body_layout.addLayout(self._form_layout)
        self._build_form()
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        self._body_layout.addWidget(buttons)

    def _build_form(self) -> None:
        raise NotImplementedError

    def _perform_action(self) -> str:
        raise NotImplementedError

    def _submit(self) -> None:
        try:
            message = self._perform_action()
        except Exception as exc:
            self._logger.exception("Flow %s failed", self.__class__.__name__)
            self.show_error(str(exc))
            return
        self.show_success(message or "Operação concluída.")


class QueryFlowDialog(BaseFlowDialog):
    """Dialog with filters and tabular results."""

    def __init__(
        self,
        services: AppServices,
        title: str,
        subtitle: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(services, title, subtitle, parent)
        filters_box = QtWidgets.QGroupBox("Filtros")
        self._filters_layout = QtWidgets.QFormLayout()
        filters_box.setLayout(self._filters_layout)
        self._body_layout.addWidget(filters_box)
        self._build_filters()
        button_row = QtWidgets.QHBoxLayout()
        self._run_button = QtWidgets.QPushButton("Executar consulta")
        self._run_button.clicked.connect(self._execute)
        button_row.addWidget(self._run_button)
        self._export_button = QtWidgets.QPushButton("Exportar CSV")
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._export_csv)
        button_row.addWidget(self._export_button)
        button_row.addStretch()
        self._body_layout.addLayout(button_row)
        self._table = QtWidgets.QTableWidget(0, 0)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._body_layout.addWidget(self._table, stretch=1)
        self._last_headers: list[str] = []
        self._last_rows: list[list[str]] = []

    def _build_filters(self) -> None:
        raise NotImplementedError

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        raise NotImplementedError

    def _execute(self) -> None:
        try:
            headers, rows = self._run_query()
        except Exception as exc:
            self._logger.exception("Query flow %s failed", self.__class__.__name__)
            self.show_error(str(exc))
            return
        self._apply_results(headers, rows)
        self.show_success(f"{len(rows)} registro(s) encontrado(s).")

    def _apply_results(
        self, headers: Sequence[str], rows: Sequence[Sequence[str]]
    ) -> None:
        self._table.clear()
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(list(headers))
        self._table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(item.flags() ^ QtCore.Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()
        self._last_headers = list(headers)
        self._last_rows = [list(row) for row in rows]
        self._export_button.setEnabled(bool(rows))

    def _export_csv(self) -> None:
        if not self._last_rows:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exportar consulta",
            str(Path.home() / "consulta.csv"),
            "CSV (*.csv)",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp, delimiter=";")
            writer.writerow(self._last_headers)
            writer.writerows(self._last_rows)
        self.show_success(f"Exportado para {path}")


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _status_label(status: RentalStatus) -> str:
    mapping = {
        RentalStatus.DRAFT: "Rascunho",
        RentalStatus.CONFIRMED: "Confirmado",
        RentalStatus.CANCELED: "Cancelado",
        RentalStatus.COMPLETED: "Concluido",
    }
    return mapping.get(status, status.value)


class _SearchableCombo(QtWidgets.QComboBox):
    """Combo box with case-insensitive contains completer."""

    def __init__(self) -> None:
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        completer = self.completer()
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)


class _CustomerSelector(QtWidgets.QWidget):
    """Reusable customer picker with search."""

    def __init__(self, flow: FlowServiceAdapter, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._flow = flow
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        filters = QtWidgets.QHBoxLayout()
        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Buscar cliente por nome")
        filters.addWidget(self._search)
        self._refresh = QtWidgets.QPushButton("Atualizar")
        filters.addWidget(self._refresh)
        layout.addLayout(filters)
        self._combo = _SearchableCombo()
        layout.addWidget(self._combo)
        self._search.textChanged.connect(self._reload)
        self._refresh.clicked.connect(self._reload)
        self._reload()

    def _reload(self) -> None:
        term = self._search.text().strip()
        customers = self._flow.list_customers(term or None)
        current_id = self.selected_customer_id()
        self._combo.blockSignals(True)
        self._combo.clear()
        for customer in customers:
            label = customer.name
            if customer.phone:
                label = f"{customer.name} ({customer.phone})"
            display = f"{label} - ID {customer.id}"
            self._combo.addItem(display, customer.id)
        self._combo.blockSignals(False)
        if current_id:
            idx = self._combo.findData(current_id)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

    def selected_customer_id(self) -> int | None:
        data = self._combo.currentData(QtCore.Qt.UserRole)
        return int(data) if data is not None else None


class _RentalSelectorWidget(QtWidgets.QWidget):
    """Widget to pick rentals with period filters."""

    def __init__(
        self,
        flow: FlowServiceAdapter,
        *,
        statuses: Sequence[RentalStatus] | None,
        parent: QtWidgets.QWidget | None = None,
        title: str | None = None,
        default_days: int = 30,
    ) -> None:
        super().__init__(parent)
        self._flow = flow
        self._statuses = tuple(statuses) if statuses else None
        self._current_rows: list = []

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        if title:
            label = QtWidgets.QLabel(title)
            label.setStyleSheet("font-weight: 600;")
            outer.addWidget(label)
        filters = QtWidgets.QHBoxLayout()
        today = QtCore.QDate.currentDate()
        self._start = QtWidgets.QDateEdit(today)
        self._start.setCalendarPopup(True)
        self._start.setDate(today.addDays(-7))
        self._end = QtWidgets.QDateEdit(today)
        self._end.setCalendarPopup(True)
        self._end.setDate(today.addDays(default_days))
        filters.addWidget(QtWidgets.QLabel("Inicio"))
        filters.addWidget(self._start)
        filters.addWidget(QtWidgets.QLabel("Fim"))
        filters.addWidget(self._end)
        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Buscar cliente ou ID")
        filters.addWidget(self._search, stretch=1)
        self._apply_button = QtWidgets.QPushButton("Filtrar")
        filters.addWidget(self._apply_button)
        outer.addLayout(filters)

        self._table = QtWidgets.QTableWidget(0, 5)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Cliente", "Periodo", "Status", "Valor/Pago"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        outer.addWidget(self._table)

        self._apply_button.clicked.connect(self._reload)
        self._search.returnPressed.connect(self._reload)
        self._reload()

    def _reload(self) -> None:
        start = _to_iso(self._start.date())
        end = _to_iso(self._end.date())
        rows = self._flow.list_rental_rows(
            start_date=start,
            end_date=end,
            statuses=self._statuses,
            search=self._search.text().strip() or None,
        )
        self._current_rows = rows
        self._table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            period = f"{row.start_date or row.event_date} a {row.end_date or row.event_date}"
            values = [
                str(row.id),
                row.customer_name,
                period,
                _status_label(row.status),
                f"{_format_currency(row.total_value)} / {_format_currency(row.paid_value)}",
            ]
            for col, value in enumerate(values):
                self._table.setItem(row_idx, col, QtWidgets.QTableWidgetItem(value))
        self._table.resizeColumnsToContents()

    def selected_rental_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._current_rows):
            return None
        return self._current_rows[row].id


# ---------------------------------------------------------------------------
# Operational flows


class NewOrderFlowDialog(ActionFlowDialog):
    """Create a draft rental or order."""

    def __init__(
        self,
        services: AppServices,
        title: str,
        subtitle: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(services, title, subtitle, parent)
        self._items_table: QtWidgets.QTableWidget
        self._products = self._flow.list_products()

    def _build_form(self) -> None:
        self._customer_selector = _CustomerSelector(self._flow)
        self._form_layout.addRow("Cliente", self._customer_selector)

        self._order_type = QtWidgets.QComboBox()
        self._order_type.addItems(["Aluguel", "Venda", "Serviço"])
        self._form_layout.addRow("Tipo", self._order_type)

        today = QtCore.QDate.currentDate()
        self._event_date = QtWidgets.QDateEdit(today)
        self._event_date.setCalendarPopup(True)
        self._form_layout.addRow("Data do evento", self._event_date)

        self._start_date = QtWidgets.QDateEdit(today)
        self._start_date.setCalendarPopup(True)
        self._form_layout.addRow("Início", self._start_date)

        self._end_date = QtWidgets.QDateEdit(today.addDays(1))
        self._end_date.setCalendarPopup(True)
        self._form_layout.addRow("Fim", self._end_date)

        self._address = QtWidgets.QLineEdit()
        self._form_layout.addRow("Endereço", self._address)

        self._contact = QtWidgets.QLineEdit()
        self._form_layout.addRow("Contato", self._contact)

        self._delivery = QtWidgets.QCheckBox("Entrega necessária / delivery")
        self._form_layout.addRow("", self._delivery)

        self._items_table = QtWidgets.QTableWidget(0, 3)
        self._items_table.setHorizontalHeaderLabels(
            ["Produto", "Quantidade", "Valor unit."]
        )
        self._items_table.horizontalHeader().setStretchLastSection(True)
        items_box = QtWidgets.QVBoxLayout()
        items_box.addWidget(self._items_table)
        buttons = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Adicionar item")
        add_btn.clicked.connect(self._append_item)
        rem_btn = QtWidgets.QPushButton("Remover item")
        rem_btn.clicked.connect(self._remove_item)
        refresh_btn = QtWidgets.QPushButton("Atualizar produtos")
        refresh_btn.clicked.connect(self._reload_products)
        buttons.addWidget(add_btn)
        buttons.addWidget(rem_btn)
        buttons.addWidget(refresh_btn)
        buttons.addStretch()
        items_box.addLayout(buttons)
        self._form_layout.addRow("Itens", items_box)

        self._notes = QtWidgets.QPlainTextEdit()
        self._notes.setPlaceholderText("Observações gerais, logística, etc.")
        self._form_layout.addRow("Observações", self._notes)

    def _reload_products(self) -> None:
        self._products = self._flow.list_products()
        for row in range(self._items_table.rowCount()):
            combo = self._items_table.cellWidget(row, 0)
            if isinstance(combo, QtWidgets.QComboBox):
                current_id = combo.currentData(QtCore.Qt.UserRole)
                self._populate_product_combo(combo, current_id=current_id)
                self._preset_product_price(row)

    def _populate_product_combo(
        self,
        combo: QtWidgets.QComboBox,
        *,
        current_id: int | None = None,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        for product in self._products:
            label = f"{product.name} (ID {product.id})"
            combo.addItem(label, product.id)
        combo.blockSignals(False)
        if current_id:
            idx = combo.findData(current_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _preset_product_price(self, row: int) -> None:
        combo = self._items_table.cellWidget(row, 0)
        price_widget = self._items_table.cellWidget(row, 2)
        if not isinstance(combo, QtWidgets.QComboBox) or not isinstance(
            price_widget, QtWidgets.QDoubleSpinBox
        ):
            return
        product = self._find_product(combo.currentData(QtCore.Qt.UserRole))
        if product and product.unit_price:
            price_widget.setValue(float(product.unit_price))

    def _find_product(self, product_id: int | None):
        if product_id is None:
            return None
        for product in self._products:
            if product.id == product_id:
                return product
        return None

    def _append_item(self) -> None:
        row = self._items_table.rowCount()
        self._items_table.insertRow(row)
        combo = _SearchableCombo()
        self._populate_product_combo(combo)
        combo.currentIndexChanged.connect(lambda _idx, r=row: self._preset_product_price(r))
        qty = QtWidgets.QSpinBox()
        qty.setRange(1, 100000)
        qty.setValue(1)
        price = QtWidgets.QDoubleSpinBox()
        price.setRange(0.01, 9_999_999.0)
        price.setDecimals(2)
        price.setPrefix("R$ ")
        self._items_table.setCellWidget(row, 0, combo)
        self._items_table.setCellWidget(row, 1, qty)
        self._items_table.setCellWidget(row, 2, price)
        self._preset_product_price(row)

    def _remove_item(self) -> None:
        row = self._items_table.currentRow()
        if row >= 0:
            self._items_table.removeRow(row)

    def _perform_action(self) -> str:
        customer_id = self._customer_selector.selected_customer_id()
        if not customer_id:
            raise ValueError("Selecione um cliente.")
        if self._items_table.rowCount() == 0:
            raise ValueError("Informe ao menos um item.")
        items = []
        total_value = 0.0
        for row in range(self._items_table.rowCount()):
            combo = self._items_table.cellWidget(row, 0)
            qty_widget = self._items_table.cellWidget(row, 1)
            price_widget = self._items_table.cellWidget(row, 2)
            if not isinstance(combo, QtWidgets.QComboBox):
                raise ValueError("Selecione um produto válido.")
            product_id = combo.currentData(QtCore.Qt.UserRole)
            if not product_id:
                raise ValueError(f"Selecione um produto na linha {row + 1}.")
            if not isinstance(qty_widget, QtWidgets.QSpinBox) or not isinstance(
                price_widget, QtWidgets.QDoubleSpinBox
            ):
                raise ValueError("Falha ao ler itens.")
            qty = qty_widget.value()
            unit_price = price_widget.value()
            if qty <= 0:
                raise ValueError("Quantidade deve ser maior que zero.")
            if unit_price <= 0:
                product = self._find_product(product_id)
                if product and product.unit_price:
                    unit_price = float(product.unit_price)
            if unit_price <= 0:
                raise ValueError("Informe o valor do item selecionado.")
            total_value += qty * unit_price
            items.append(
                {"product_id": product_id, "qty": qty, "unit_price": unit_price}
            )
        rental = self._flow.create_draft_order(
            customer_id=customer_id,
            event_date=_to_iso(self._event_date.date()),
            start_date=_to_iso(self._start_date.date()),
            end_date=_to_iso(self._end_date.date()),
            address=self._address.text().strip() or None,
            contact_phone=self._contact.text().strip() or None,
            delivery_required=self._delivery.isChecked(),
            items=items,
            total_value=total_value,
        )
        return f"Pedido #{rental.id or '?'} criado como rascunho."


class CloseOrderFlowDialog(ActionFlowDialog):
    """Complete a rental/order."""

    def _build_form(self) -> None:
        self._selector = _RentalSelectorWidget(
            self._flow,
            statuses=(RentalStatus.DRAFT, RentalStatus.CONFIRMED),
            title="Selecione o pedido",
        )
        self._form_layout.addRow("Pedido", self._selector)
        self._notes = QtWidgets.QLineEdit()
        self._form_layout.addRow("Observações", self._notes)

    def _perform_action(self) -> str:
        rid = self._selector.selected_rental_id()
        if not rid:
            raise ValueError("Selecione um pedido.")
        self._flow.complete_rental(rid)
        return f"Pedido #{rid} encerrado com sucesso."


class ReturnFlowDialog(ActionFlowDialog):
    """Register returned items."""

    def _build_form(self) -> None:
        self._selector = _RentalSelectorWidget(
            self._flow,
            statuses=(RentalStatus.CONFIRMED,),
            title="Pedidos confirmados",
        )
        self._form_layout.addRow("Pedido", self._selector)
        self._return_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._return_date.setCalendarPopup(True)
        self._form_layout.addRow("Data da devolução", self._return_date)
        self._notes = QtWidgets.QPlainTextEdit()
        self._notes.setPlaceholderText("Condições dos itens, observações etc.")
        self._form_layout.addRow("Relato", self._notes)

    def _perform_action(self) -> str:
        rid = self._selector.selected_rental_id()
        if not rid:
            raise ValueError("Selecione um pedido.")
        self._flow.complete_rental(rid)
        return f"Devolução registrada para o pedido #{rid} em {_to_iso(self._return_date.date())}."


class UpdateStockFlowDialog(ActionFlowDialog):
    """Adjust item quantity."""

    def _build_form(self) -> None:
        self._products = self._flow.list_products()
        self._product_combo = _SearchableCombo()
        self._form_layout.addRow("Produto", self._product_combo)
        self._new_total = QtWidgets.QSpinBox()
        self._new_total.setRange(0, 100000)
        self._form_layout.addRow("Quantidade disponível", self._new_total)
        self._reason = QtWidgets.QLineEdit()
        self._form_layout.addRow("Motivo", self._reason)
        self._reload_products()
        self._product_combo.currentIndexChanged.connect(self._sync_current_qty)

    def _reload_products(self) -> None:
        self._products = self._flow.list_products()
        current_id = self.selected_product_id()
        self._product_combo.blockSignals(True)
        self._product_combo.clear()
        for product in self._products:
            label = f"{product.name} - estoque {product.total_qty}"
            self._product_combo.addItem(label, product.id)
        self._product_combo.blockSignals(False)
        if current_id:
            idx = self._product_combo.findData(current_id)
            if idx >= 0:
                self._product_combo.setCurrentIndex(idx)
        self._sync_current_qty()

    def _sync_current_qty(self) -> None:
        product = self._selected_product()
        if product:
            self._new_total.setValue(int(product.total_qty))

    def selected_product_id(self) -> int | None:
        data = self._product_combo.currentData(QtCore.Qt.UserRole)
        return int(data) if data is not None else None

    def _selected_product(self):
        product_id = self.selected_product_id()
        if product_id is None:
            return None
        for product in self._products:
            if product.id == product_id:
                return product
        return None

    def _perform_action(self) -> str:
        product = self._selected_product()
        if not product or not product.id:
            raise ValueError("Selecione um produto.")
        updated = self._flow.update_stock(product.id, self._new_total.value())
        return f"Quantidade do item '{updated.name}' ajustada para {self._new_total.value()}."


# ---------------------------------------------------------------------------
# Finance flows


class RegisterIncomeFlowDialog(ActionFlowDialog):
    """Register a payment entry."""

    def _build_form(self) -> None:
        self._selector = _RentalSelectorWidget(
            self._flow,
            statuses=(RentalStatus.DRAFT, RentalStatus.CONFIRMED, RentalStatus.COMPLETED),
            title="Selecione o pedido",
        )
        self._form_layout.addRow("Pedido", self._selector)
        self._amount = QtWidgets.QDoubleSpinBox()
        self._amount.setRange(0.01, 9_999_999.0)
        self._amount.setPrefix("R$ ")
        self._amount.setDecimals(2)
        self._form_layout.addRow("Valor recebido", self._amount)
        self._method = QtWidgets.QComboBox()
        self._method.setEditable(True)
        self._method.addItems(["PIX", "Cartão", "Dinheiro", "Transferência"])
        self._form_layout.addRow("Forma de pagamento", self._method)
        self._paid_at = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._paid_at.setCalendarPopup(True)
        self._form_layout.addRow("Data", self._paid_at)
        self._note = QtWidgets.QLineEdit()
        self._form_layout.addRow("Observação", self._note)

    def _perform_action(self) -> str:
        rental_id = self._selector.selected_rental_id()
        if not rental_id:
            raise ValueError("Selecione um pedido.")
        payment = self._flow.register_payment(
            rental_id=rental_id,
            amount=self._amount.value(),
            method=self._method.currentText() or None,
            paid_at=_to_iso(self._paid_at.date()),
            note=self._note.text().strip() or None,
        )
        return f"Pagamento #{payment.id or '?'} registrado."


class RegisterExpenseFlowDialog(ActionFlowDialog):
    """Register a new outgoing expense."""

    def _build_form(self) -> None:
        self._date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._form_layout.addRow("Data", self._date)
        self._category = QtWidgets.QLineEdit()
        self._form_layout.addRow("Categoria", self._category)
        self._description = QtWidgets.QLineEdit()
        self._form_layout.addRow("Descrição", self._description)
        self._amount = QtWidgets.QDoubleSpinBox()
        self._amount.setRange(0.01, 9_999_999.0)
        self._amount.setPrefix("R$ ")
        self._amount.setDecimals(2)
        self._form_layout.addRow("Valor", self._amount)
        self._method = QtWidgets.QLineEdit()
        self._form_layout.addRow("Forma de pagamento", self._method)
        self._supplier = QtWidgets.QLineEdit()
        self._form_layout.addRow("Fornecedor", self._supplier)
        self._notes = QtWidgets.QPlainTextEdit()
        self._notes.setPlaceholderText("Observações (NF, comprovante etc.)")
        self._form_layout.addRow("Observações", self._notes)

    def _perform_action(self) -> str:
        expense = self._flow.register_expense(
            date=_to_iso(self._date.date()),
            category=self._category.text().strip() or None,
            description=self._description.text().strip() or None,
            amount=self._amount.value(),
            payment_method=self._method.text().strip() or None,
            supplier=self._supplier.text().strip() or None,
            notes=self._notes.toPlainText().strip() or None,
        )
        return f"Despesa #{expense.id or '?'} registrada."


class FinanceReportFlowDialog(QueryFlowDialog):
    """Detailed finance overview."""

    def _build_filters(self) -> None:
        today = QtCore.QDate.currentDate()
        self._start = QtWidgets.QDateEdit(today.addDays(-7))
        self._start.setCalendarPopup(True)
        self._filters_layout.addRow("Início", self._start)
        self._end = QtWidgets.QDateEdit(today)
        self._end.setCalendarPopup(True)
        self._filters_layout.addRow("Fim", self._end)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        start = _to_iso(self._start.date())
        end = _to_iso(self._end.date())
        report = self._flow.get_finance_report(start, end)
        rows = [
            [
                "Recebido",
                _format_currency(report.total_received),
                "",
                "",
                "",
                "",
            ],
            [
                "A receber (confirmados)",
                _format_currency(report.total_to_receive),
                "",
                "",
                "",
                "",
            ],
            ["Pedidos analisados", str(report.rentals_count), "", "", "", ""],
        ]
        details = self._flow.list_finance_details(start, end)
        for rental in details:
            period = f"{rental.start_date or rental.event_date} a {rental.end_date or rental.event_date}"
            rows.append(
                [
                    f"Pedido #{rental.id}",
                    rental.customer_name,
                    rental.status.value,
                    _format_currency(rental.total_value),
                    f"Pago: {_format_currency(rental.paid_value)}",
                    period,
                ]
            )
        headers = ["Indicador/Pedido", "Cliente", "Status", "Valor", "Pago", "Periodo"]
        return headers, rows


class CashSummaryFlowDialog(QueryFlowDialog):
    """Compare received amounts and expenses."""

    def _build_filters(self) -> None:
        today = QtCore.QDate.currentDate()
        self._start = QtWidgets.QDateEdit(today.addDays(-30))
        self._start.setCalendarPopup(True)
        self._filters_layout.addRow("Início", self._start)
        self._end = QtWidgets.QDateEdit(today)
        self._end.setCalendarPopup(True)
        self._filters_layout.addRow("Fim", self._end)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        start = _to_iso(self._start.date())
        end = _to_iso(self._end.date())
        report = self._flow.get_finance_report(start, end)
        expenses = self._services.expense_service.get_total_by_period(start, end)
        rows = [
            [
                "Recebido",
                _format_currency(report.total_received),
            ],
            [
                "Despesas",
                _format_currency(expenses),
            ],
            [
                "Saldo estimado",
                _format_currency(report.total_received - expenses),
            ],
            [
                "A receber (confirmados)",
                _format_currency(report.total_to_receive),
            ],
        ]
        headers = ["Indicador", "Valor"]
        return headers, rows


# ---------------------------------------------------------------------------
# Client flows


class NewClientFlowDialog(ActionFlowDialog):
    """Create a client record."""

    def _build_form(self) -> None:
        self._name = QtWidgets.QLineEdit()
        self._form_layout.addRow("Nome", self._name)
        self._phone = QtWidgets.QLineEdit()
        self._form_layout.addRow("Telefone", self._phone)
        self._notes = QtWidgets.QPlainTextEdit()
        self._form_layout.addRow("Notas", self._notes)

    def _perform_action(self) -> str:
        name = self._name.text().strip()
        if not name:
            raise ValueError("Informe o nome do cliente.")
        customer = self._flow.create_customer(
            name=name,
            phone=self._phone.text().strip() or None,
            notes=self._notes.toPlainText().strip() or None,
        )
        return f"Cliente #{customer.id or '?'} cadastrado."


class SearchClientFlowDialog(QueryFlowDialog):
    """Search clients by name."""

    def _build_filters(self) -> None:
        self._term = QtWidgets.QLineEdit()
        self._filters_layout.addRow("Nome/termo", self._term)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        term = self._term.text().strip()
        customers = self._flow.list_customers(term or None)
        rows = [
            [
                str(customer.id or ""),
                customer.name,
                customer.phone or "",
                (customer.created_at or "")[:10],
            ]
            for customer in customers
        ]
        headers = ["ID", "Nome", "Telefone", "Criado em"]
        return headers, rows


class ClientHistoryFlowDialog(QueryFlowDialog):
    """List rentals linked to a client."""

    def _build_filters(self) -> None:
        self._customer_selector = _CustomerSelector(self._flow)
        self._filters_layout.addRow("Cliente", self._customer_selector)
        today = QtCore.QDate.currentDate()
        self._start = QtWidgets.QDateEdit(today.addMonths(-6))
        self._start.setCalendarPopup(True)
        self._filters_layout.addRow("Início", self._start)
        self._end = QtWidgets.QDateEdit(today)
        self._end.setCalendarPopup(True)
        self._filters_layout.addRow("Fim", self._end)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        customer_id = self._customer_selector.selected_customer_id()
        if not customer_id:
            raise ValueError("Selecione um cliente.")
        start = _to_iso(self._start.date())
        end = _to_iso(self._end.date())
        rentals = self._flow.list_customer_history(customer_id, start, end)
        result = []
        for rental in rentals:
            period = f"{rental.start_date or rental.event_date} a {rental.end_date or rental.event_date}"
            result.append(
                [
                    str(rental.id),
                    period,
                    rental.status.value,
                    _format_currency(rental.total_value),
                    f"Pago {_format_currency(rental.paid_value)}",
                ]
            )
        headers = ["Pedido", "Periodo", "Status", "Valor", "Pago"]
        return headers, result


class ClientsByPeriodFlowDialog(QueryFlowDialog):
    """List clients created between dates."""

    def _build_filters(self) -> None:
        today = QtCore.QDate.currentDate()
        self._start = QtWidgets.QDateEdit(today.addMonths(-1))
        self._start.setCalendarPopup(True)
        self._filters_layout.addRow("Início", self._start)
        self._end = QtWidgets.QDateEdit(today)
        self._end.setCalendarPopup(True)
        self._filters_layout.addRow("Fim", self._end)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        customers = self._flow.list_customers_by_period(
            _to_iso(self._start.date()),
            _to_iso(self._end.date()),
        )
        result = []
        for customer in customers:
            created = (customer.created_at or "")[:10] if customer.created_at else ""
            result.append(
                [
                    str(customer.id or ""),
                    customer.name,
                    customer.phone or "",
                    created,
                ]
            )
        headers = ["ID", "Nome", "Telefone", "Criado em"]
        return headers, result


# ---------------------------------------------------------------------------
# Agenda flows


class _AgendaBaseDialog(QueryFlowDialog):
    """Shared helper to fetch agenda rows."""

    def _build_filters(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _fetch(self, start: str, end: str) -> list[list[str]]:
        rows = self._flow.list_agenda_rows(start, end)
        result: list[list[str]] = []
        for row in rows:
            period = f"{row.start_date or row.event_date} a {row.end_date or row.event_date}"
            result.append(
                [
                    str(row.id),
                    row.customer_name,
                    period,
                    row.status.value,
                    f"R$ {row.total_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                ]
            )
        return result


class AgendaTodayFlowDialog(_AgendaBaseDialog):
    """Agenda para data única."""

    def _build_filters(self) -> None:
        self._date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._filters_layout.addRow("Data", self._date)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        day = _to_iso(self._date.date())
        rows = self._fetch(day, day)
        headers = ["Pedido", "Cliente", "Período", "Status", "Valor"]
        return headers, rows


class AgendaWeekFlowDialog(_AgendaBaseDialog):
    """Agenda para sete dias."""

    def _build_filters(self) -> None:
        self._start = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._start.setCalendarPopup(True)
        self._filters_layout.addRow("Início da semana", self._start)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        start_date = self._start.date()
        end_date = start_date.addDays(6)
        rows = self._fetch(_to_iso(start_date), _to_iso(end_date))
        headers = ["Pedido", "Cliente", "Período", "Status", "Valor"]
        return headers, rows


class AgendaCustomFlowDialog(_AgendaBaseDialog):
    """Agenda personalizada."""

    def _build_filters(self) -> None:
        today = QtCore.QDate.currentDate()
        self._start = QtWidgets.QDateEdit(today)
        self._start.setCalendarPopup(True)
        self._filters_layout.addRow("Início", self._start)
        self._end = QtWidgets.QDateEdit(today.addDays(7))
        self._end.setCalendarPopup(True)
        self._filters_layout.addRow("Fim", self._end)

    def _run_query(self) -> tuple[list[str], list[list[str]]]:
        rows = self._fetch(_to_iso(self._start.date()), _to_iso(self._end.date()))
        headers = ["Pedido", "Cliente", "Período", "Status", "Valor"]
        return headers, rows


# ---------------------------------------------------------------------------
# Helper for Assistant screen


def _action_def(
    code: str,
    title: str,
    desc: str,
    dialog_cls: type[ActionFlowDialog],
) -> FlowDefinition:
    return FlowDefinition(
        code=code,
        title=title,
        description=desc,
        dialog_factory=lambda services, parent, _cls=dialog_cls, _title=title, _desc=desc: _cls(
            services, title=_title, subtitle=_desc, parent=parent
        ),
    )


def _query_def(
    code: str,
    title: str,
    desc: str,
    dialog_cls: type[QueryFlowDialog],
) -> FlowDefinition:
    return FlowDefinition(
        code=code,
        title=title,
        description=desc,
        dialog_factory=lambda services, parent, _cls=dialog_cls, _title=title, _desc=desc: _cls(
            services, title=_title, subtitle=_desc, parent=parent
        ),
    )


def get_default_categories() -> list[FlowCategory]:
    """Return grouped flow definitions used by the Assistant."""

    operational = FlowCategory(
        name="Operacional",
        flows=[
            _action_def(
                "new_order",
                "Novo Pedido",
                "Crie um pedido de aluguel, venda ou serviço diretamente.",
                NewOrderFlowDialog,
            ),
            _action_def(
                "close_order",
                "Encerrar Pedido",
                "Finalize pedidos confirmados após revisão.",
                CloseOrderFlowDialog,
            ),
            _action_def(
                "register_return",
                "Registrar Devolução",
                "Anote a devolução de itens com data e observações.",
                ReturnFlowDialog,
            ),
            _action_def(
                "update_stock",
                "Atualizar Estoque",
                "Ajuste rapidamente a quantidade disponível de um item.",
                UpdateStockFlowDialog,
            ),
        ],
    )
    finance = FlowCategory(
        name="Financeiro",
        flows=[
            _action_def(
                "register_income",
                "Registrar Entrada",
                "Adicione um recebimento vinculado ao pedido selecionado.",
                RegisterIncomeFlowDialog,
            ),
            _action_def(
                "register_expense",
                "Registrar Saída",
                "Registre despesas operacionais com categoria e fornecedor.",
                RegisterExpenseFlowDialog,
            ),
            _query_def(
                "finance_report",
                "Gerar Relatório Financeiro",
                "Resumo completo dos pedidos e recebimentos do período.",
                FinanceReportFlowDialog,
            ),
            _query_def(
                "cash_summary",
                "Resumo de Caixa",
                "Compare recebidos, despesas e saldo projetado.",
                CashSummaryFlowDialog,
            ),
        ],
    )
    clients = FlowCategory(
        name="Clientes",
        flows=[
            _action_def(
                "new_client",
                "Novo Cliente",
                "Cadastre clientes com contato e observações.",
                NewClientFlowDialog,
            ),
            _query_def(
                "search_client",
                "Consultar Cliente",
                "Busque clientes por nome e visualize contatos.",
                SearchClientFlowDialog,
            ),
            _query_def(
                "client_history",
                "Histórico de Cliente",
                "Listagem de pedidos e valores associados ao cliente.",
                ClientHistoryFlowDialog,
            ),
            _query_def(
                "clients_period",
                "Clientes do período",
                "Clientes cadastrados entre as datas informadas.",
                ClientsByPeriodFlowDialog,
            ),
        ],
    )
    agenda = FlowCategory(
        name="Agenda",
        flows=[
            _query_def(
                "agenda_today",
                "Agenda de Hoje",
                "Verifique retiradas e devoluções do dia selecionado.",
                AgendaTodayFlowDialog,
            ),
            _query_def(
                "agenda_week",
                "Agenda da Semana",
                "Planejamento dos próximos sete dias a partir da data base.",
                AgendaWeekFlowDialog,
            ),
            _query_def(
                "agenda_custom",
                "Agenda por período",
                "Consulta personalizada com início/fim escolhidos.",
                AgendaCustomFlowDialog,
            ),
        ],
    )
    return [operational, finance, clients, agenda]
