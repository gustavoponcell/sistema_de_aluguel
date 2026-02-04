"""Screen for product inventory management."""

from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from rental_manager.domain.models import Product, ProductKind, SERVICE_DEFAULT_QTY
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.ui.strings import (
    LABEL_STOCK_AVAILABLE,
    LABEL_STOCK_IN_USE,
    LABEL_STOCK_TOTAL,
    LABEL_STOCK_TYPE,
    TERM_ITEM,
    TITLE_CONFIRMATION,
    TITLE_ERROR,
    TITLE_WARNING,
    product_kind_label,
)


class ProductDialog(QtWidgets.QDialog):
    """Dialog for creating or editing a product."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        product: Optional[Product] = None,
    ) -> None:
        super().__init__(parent)
        self._product = product
        self.setWindowTitle("Item")
        self.setModal(True)
        self._build_ui()
        if product:
            self._load_product(product)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.name_input = QtWidgets.QLineEdit()
        self.category_input = QtWidgets.QLineEdit()
        self.kind_input = QtWidgets.QComboBox()
        self.kind_input.addItem("Aluguel", ProductKind.RENTAL)
        self.kind_input.addItem("Venda", ProductKind.SALE)
        self.kind_input.addItem("Serviço", ProductKind.SERVICE)
        self.kind_input.currentIndexChanged.connect(self._on_kind_changed)
        self.total_qty_input = QtWidgets.QSpinBox()
        self.total_qty_input.setRange(0, 1_000_000)
        self.total_qty_input.setSingleStep(1)
        self.unit_price_input = QtWidgets.QDoubleSpinBox()
        self.unit_price_input.setRange(0.0, 1_000_000.0)
        self.unit_price_input.setDecimals(2)
        self.unit_price_input.setSingleStep(1.0)
        self.unit_price_input.setPrefix("R$ ")
        self.qty_hint = QtWidgets.QLabel(
            "Para serviços, a disponibilidade é alta e não bloqueia pedidos."
        )
        self.qty_hint.setStyleSheet("color: #666; font-size: 12px;")
        self.qty_hint.setWordWrap(True)
        self.qty_hint.setVisible(False)

        form.addRow(f"Nome do {TERM_ITEM.lower()}:", self.name_input)
        form.addRow("Categoria:", self.category_input)
        form.addRow("Tipo:", self.kind_input)
        form.addRow("Quantidade total:", self.total_qty_input)
        form.addRow("", self.qty_hint)
        form.addRow("Preço padrão:", self.unit_price_input)

        layout.addLayout(form)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

        layout.addWidget(self.button_box)
        self._on_kind_changed()

    def _load_product(self, product: Product) -> None:
        self.name_input.setText(product.name)
        self.category_input.setText(product.category or "")
        self.total_qty_input.setValue(product.total_qty)
        self.unit_price_input.setValue(product.unit_price or 0.0)
        if product.kind == ProductKind.SERVICE:
            index = 2
        elif product.kind == ProductKind.SALE:
            index = 1
        else:
            index = 0
        self.kind_input.setCurrentIndex(index)
        self._on_kind_changed()

    def _on_kind_changed(self) -> None:
        kind = self.kind_input.currentData()
        is_service = kind == ProductKind.SERVICE
        self.total_qty_input.setEnabled(not is_service)
        if is_service:
            self.total_qty_input.setValue(SERVICE_DEFAULT_QTY)
        elif self.total_qty_input.value() == SERVICE_DEFAULT_QTY:
            self.total_qty_input.setValue(1)
        self.qty_hint.setVisible(is_service)

    def _on_accept(self) -> None:
        if not self._validate():
            return
        self.accept()

    def _validate(self) -> bool:
        name = self.name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                TITLE_WARNING,
                "Informe o nome do item.",
            )
            return False
        category = self.category_input.text().strip()
        if not category:
            QtWidgets.QMessageBox.warning(
                self,
                TITLE_WARNING,
                "Informe a categoria do item.",
            )
            return False
        kind = self.kind_input.currentData()
        if kind in (ProductKind.RENTAL, ProductKind.SALE) and self.total_qty_input.value() <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                TITLE_WARNING,
                "A quantidade total deve ser maior que zero.",
            )
            return False
        if self.unit_price_input.value() <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                TITLE_WARNING,
                "O preço padrão deve ser maior que zero.",
            )
            return False
        return True

    def get_data(self) -> dict[str, object]:
        return {
            "name": self.name_input.text().strip(),
            "category": self.category_input.text().strip(),
            "total_qty": self.total_qty_input.value(),
            "unit_price": float(self.unit_price_input.value()),
            "kind": self.kind_input.currentData(),
        }


class ProductsScreen(BaseScreen):
    """Screen for products/stock."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._products: List[Product] = []
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.refresh)
        self._filter_timer = QtCore.QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(250)
        self._filter_timer.timeout.connect(self.refresh)
        self._build_ui()
        self._load_products()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Estoque")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Gerencie produtos e serviços, ajuste quantidades e acompanhe a disponibilidade."
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Data de referência:"))
        self.reference_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.reference_date_input.setCalendarPopup(True)
        self.reference_date_input.setDisplayFormat("dd/MM/yyyy")
        self.reference_date_input.dateChanged.connect(self._on_reference_date_changed)
        filter_layout.addWidget(self.reference_date_input)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Buscar:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Digite o nome do item")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        button_layout = QtWidgets.QHBoxLayout()
        self.new_button = QtWidgets.QPushButton("Novo item")
        self.edit_button = QtWidgets.QPushButton("Editar")
        self.deactivate_button = QtWidgets.QPushButton("Desativar")
        self.edit_button.setEnabled(False)
        self.deactivate_button.setEnabled(False)
        self.new_button.clicked.connect(self._on_new)
        self.edit_button.clicked.connect(self._on_edit)
        self.deactivate_button.clicked.connect(self._on_deactivate)
        button_layout.addWidget(self.new_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.deactivate_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [TERM_ITEM, LABEL_STOCK_TYPE, LABEL_STOCK_TOTAL, LABEL_STOCK_IN_USE, LABEL_STOCK_AVAILABLE]
        )
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

    def _on_search_changed(self, text: str) -> None:
        self._pending_search = text
        self._search_timer.start()

    def _on_reference_date_changed(self) -> None:
        self._filter_timer.start()

    def refresh(self) -> None:
        self._load_products(getattr(self, "_pending_search", self.search_input.text()))

    def _load_products(self, term: str = "") -> None:
        try:
            if term.strip():
                products = self._services.product_repo.search_by_name(term)
            else:
                products = self._services.product_repo.list_active()
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                TITLE_ERROR,
                "Não foi possível carregar os itens.",
            )
            return
        self._products = products
        self._render_table(products)

    def _render_table(self, products: List[Product]) -> None:
        reference_date = self.reference_date_input.date().toPython()
        self.table.setRowCount(len(products))
        for row, product in enumerate(products):
            is_service = product.kind == ProductKind.SERVICE
            is_sale = product.kind == ProductKind.SALE
            if is_service:
                reserved_qty = None
                available_qty = None
            elif is_sale:
                reserved_qty = None
                available_qty = self._services.inventory_service.get_sale_available_qty(
                    product.id or 0
                )
            else:
                reserved_qty = self._services.inventory_service.on_loan(
                    product.id or 0, reference_date
                )
                available_qty = self._services.inventory_service.available(
                    product.id or 0, reference_date
                )
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(product.name))
            self.table.setItem(
                row, 1, QtWidgets.QTableWidgetItem(product_kind_label(product.kind))
            )
            self.table.setItem(
                row,
                2,
                QtWidgets.QTableWidgetItem(
                    "—" if is_service else str(product.total_qty)
                ),
            )
            self.table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem("—" if reserved_qty is None else str(reserved_qty)),
            )
            self.table.setItem(
                row,
                4,
                QtWidgets.QTableWidgetItem(
                    "Sem controle de estoque"
                    if is_service
                    else str(available_qty)
                ),
            )
        self.table.setSortingEnabled(False)
        self.table.resizeRowsToContents()
        self._on_selection_changed()

    def _get_selected_product(self) -> Optional[Product]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self._products):
            return None
        return self._products[row]

    def _on_selection_changed(self) -> None:
        has_selection = self._get_selected_product() is not None
        self.edit_button.setEnabled(has_selection)
        self.deactivate_button.setEnabled(has_selection)

    def _on_new(self) -> None:
        dialog = ProductDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            self._services.product_repo.create(
                name=str(data["name"]),
                category=str(data["category"]),
                total_qty=int(data["total_qty"]),
                unit_price=float(data["unit_price"]),
                kind=data["kind"],
                active=True,
            )
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                TITLE_ERROR,
                "Não foi possível salvar o item. Verifique os dados e tente novamente.",
            )
            return
        self._services.data_bus.data_changed.emit()
        self._load_products(self.search_input.text())

    def _on_edit(self) -> None:
        product = self._get_selected_product()
        if not product:
            return
        dialog = ProductDialog(self, product=product)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            updated = self._services.product_repo.update(
                product_id=product.id or 0,
                name=str(data["name"]),
                category=str(data["category"]),
                total_qty=int(data["total_qty"]),
                unit_price=float(data["unit_price"]),
                kind=data["kind"],
                active=True,
            )
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                TITLE_ERROR,
                "Não foi possível atualizar o item. Tente novamente.",
            )
            return
        if not updated:
            QtWidgets.QMessageBox.warning(
                self,
                TITLE_WARNING,
                "O item não foi encontrado para atualização.",
            )
        self._services.data_bus.data_changed.emit()
        self._load_products(self.search_input.text())

    def _on_deactivate(self) -> None:
        product = self._get_selected_product()
        if not product:
            return
        response = QtWidgets.QMessageBox.question(
            self,
            TITLE_CONFIRMATION,
            f"Tem certeza que deseja desativar o item '{product.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if response != QtWidgets.QMessageBox.Yes:
            return
        try:
            success = self._services.product_repo.soft_delete(product.id or 0)
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                TITLE_ERROR,
                "Não foi possível desativar o item. Tente novamente.",
            )
            return
        if not success:
            QtWidgets.QMessageBox.warning(
                self,
                TITLE_WARNING,
                "O item já estava desativado ou não foi encontrado.",
            )
        self._services.data_bus.data_changed.emit()
        self._load_products(self.search_input.text())
