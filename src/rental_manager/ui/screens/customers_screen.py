"""Screen for customer management."""

from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from rental_manager.domain.models import Customer
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.ui.strings import TITLE_ERROR, TITLE_WARNING
from rental_manager.utils.theme import apply_table_theme


class CustomerDialog(QtWidgets.QDialog):
    """Dialog for creating or editing a customer."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        customer: Optional[Customer] = None,
    ) -> None:
        super().__init__(parent)
        self._customer = customer
        self.setWindowTitle("Cliente")
        self.setModal(True)
        self._build_ui()
        if customer:
            self._load_customer(customer)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.name_input = QtWidgets.QLineEdit()
        self.phone_input = QtWidgets.QLineEdit()
        self.phone_input.setPlaceholderText("(00) 00000-0000")
        self.notes_input = QtWidgets.QPlainTextEdit()
        self.notes_input.setPlaceholderText("Observações adicionais")
        self.notes_input.setFixedHeight(100)

        form.addRow("Nome:", self.name_input)
        form.addRow("Telefone:", self.phone_input)
        form.addRow("Observações:", self.notes_input)

        layout.addLayout(form)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _load_customer(self, customer: Customer) -> None:
        self.name_input.setText(customer.name)
        self.phone_input.setText(customer.phone or "")
        self.notes_input.setPlainText(customer.notes or "")

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
                "Informe o nome do cliente.",
            )
            return False
        return True

    def get_data(self) -> dict[str, Optional[str]]:
        return {
            "name": self.name_input.text().strip(),
            "phone": self.phone_input.text().strip() or None,
            "notes": self.notes_input.toPlainText().strip() or None,
        }


class CustomersScreen(BaseScreen):
    """Screen for customers."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._customers: List[Customer] = []
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.refresh)
        self._build_ui()
        self._load_customers()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Clientes")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Cadastre clientes e acompanhe o histórico de pedidos."
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Buscar:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Digite o nome do cliente")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        button_layout = QtWidgets.QHBoxLayout()
        self.new_button = QtWidgets.QPushButton("Novo")
        self.edit_button = QtWidgets.QPushButton("Editar")
        self.delete_button = QtWidgets.QPushButton("Excluir")
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.new_button.clicked.connect(self._on_new)
        self.edit_button.clicked.connect(self._on_edit)
        self.delete_button.clicked.connect(self._on_delete)
        button_layout.addWidget(self.new_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nome", "Telefone", "Observações"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        apply_table_theme(
            self.table, "dark" if self._services.theme_manager.is_dark() else "light"
        )
        self._services.theme_manager.theme_changed.connect(
            lambda theme, table=self.table: apply_table_theme(table, theme)
        )
        layout.addWidget(self.table)

    def _on_search_changed(self, text: str) -> None:
        self._schedule_refresh(text)

    def _schedule_refresh(self, text: str) -> None:
        self._pending_search = text
        self._search_timer.start()

    def refresh(self) -> None:
        self._load_customers(getattr(self, "_pending_search", self.search_input.text()))

    def _load_customers(self, term: str = "") -> None:
        try:
            if term.strip():
                customers = self._services.customer_repo.search_by_name(term)
            else:
                customers = self._services.customer_repo.list_all()
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                TITLE_ERROR,
                "Não foi possível carregar os clientes.",
            )
            return
        self._customers = customers
        self._render_table(customers)

    def _render_table(self, customers: List[Customer]) -> None:
        self.table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(customer.name))
            self.table.setItem(
                row,
                1,
                QtWidgets.QTableWidgetItem(customer.phone or "—"),
            )
            self.table.setItem(
                row,
                2,
                QtWidgets.QTableWidgetItem(customer.notes or "—"),
            )
        self.table.setSortingEnabled(False)
        self.table.resizeRowsToContents()
        self._on_selection_changed()

    def _get_selected_customer(self) -> Optional[Customer]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self._customers):
            return None
        return self._customers[row]

    def _on_selection_changed(self) -> None:
        has_selection = self._get_selected_customer() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _on_new(self) -> None:
        dialog = CustomerDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            self._services.customer_repo.create(
                name=data["name"] or "",
                phone=data["phone"],
                notes=data["notes"],
            )
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível salvar o cliente. Verifique os dados e tente novamente.",
            )
            return
        self._services.data_bus.data_changed.emit()
        self._load_customers(self.search_input.text())

    def _on_edit(self) -> None:
        customer = self._get_selected_customer()
        if not customer:
            return
        dialog = CustomerDialog(self, customer=customer)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            updated = self._services.customer_repo.update(
                customer_id=customer.id or 0,
                name=data["name"] or "",
                phone=data["phone"],
                notes=data["notes"],
            )
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível atualizar o cliente. Tente novamente.",
            )
            return
        if not updated:
            QtWidgets.QMessageBox.warning(
                self,
                "Atenção",
                "O cliente não foi encontrado para atualização.",
            )
        self._services.data_bus.data_changed.emit()
        self._load_customers(self.search_input.text())

    def _on_delete(self) -> None:
        customer = self._get_selected_customer()
        if not customer:
            return
        response = QtWidgets.QMessageBox.question(
            self,
            "Confirmação",
            f"Tem certeza que deseja excluir o cliente '{customer.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if response != QtWidgets.QMessageBox.Yes:
            return
        try:
            success = self._services.customer_repo.delete(customer.id or 0)
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível excluir o cliente. Tente novamente.",
            )
            return
        if not success:
            QtWidgets.QMessageBox.warning(
                self,
                "Atenção",
                "O cliente já havia sido removido ou não foi encontrado.",
            )
        self._services.data_bus.data_changed.emit()
        self._load_customers(self.search_input.text())
