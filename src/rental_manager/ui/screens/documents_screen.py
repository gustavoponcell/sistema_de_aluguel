"""Screen for documents listing and actions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.domain.models import Customer, Document, DocumentType, Rental
from rental_manager.logging_config import get_logger
from rental_manager.paths import get_config_path
from rental_manager.repositories import rental_repo
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.utils.documents import (
    DocumentsSettings,
    build_document_filename,
    load_documents_settings,
    save_documents_settings,
)
from rental_manager.utils.pdf_generator import generate_rental_pdf
from rental_manager.utils.theme import apply_table_theme


def _format_date(value: Optional[str]) -> str:
    if not value:
        return "—"
    date_value = QtCore.QDate.fromString(value, "yyyy-MM-dd")
    if date_value.isValid():
        return date_value.toString("dd/MM/yyyy")
    date_time = QtCore.QDateTime.fromString(value, "yyyy-MM-ddTHH:mm:ss")
    if not date_time.isValid():
        date_time = QtCore.QDateTime.fromString(value, "yyyy-MM-dd HH:mm:ss")
    if date_time.isValid():
        return date_time.toString("dd/MM/yyyy HH:mm")
    return value


def _document_type_label(doc_type: DocumentType) -> str:
    mapping = {
        DocumentType.CONTRACT: "Contrato",
        DocumentType.RECEIPT: "Recibo",
        DocumentType.INVOICE: "Nota fiscal",
    }
    return mapping.get(doc_type, doc_type.value)


class DocumentsScreen(BaseScreen):
    """Screen for documents listing."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._logger = get_logger(self.__class__.__name__)
        self._config_path = get_config_path()
        self._documents: list[Document] = []
        self._filter_timer = QtCore.QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(250)
        self._filter_timer.timeout.connect(self.refresh)
        self._build_ui()
        self._load_documents()

    def refresh(self) -> None:
        self._load_documents()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Documentos")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        subtitle = QtWidgets.QLabel(
            "Consulte contratos, notas fiscais e recibos gerados no sistema."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #555; font-size: 14px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        filters_group = QtWidgets.QGroupBox("Filtros")
        filters_layout = QtWidgets.QGridLayout(filters_group)
        filters_layout.setVerticalSpacing(12)
        filters_layout.setHorizontalSpacing(12)

        self._date_filter_check = QtWidgets.QCheckBox("Filtrar por período")
        self._start_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._start_date_input.setCalendarPopup(True)
        self._start_date_input.setDisplayFormat("dd/MM/yyyy")
        self._end_date_input = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._end_date_input.setCalendarPopup(True)
        self._end_date_input.setDisplayFormat("dd/MM/yyyy")
        self._start_date_input.setEnabled(False)
        self._end_date_input.setEnabled(False)

        self._type_combo = QtWidgets.QComboBox()
        self._type_combo.addItem("Todos", None)
        self._type_combo.addItem("Contrato", DocumentType.CONTRACT)
        self._type_combo.addItem("Nota fiscal", DocumentType.INVOICE)
        self._type_combo.addItem("Recibo", DocumentType.RECEIPT)

        self._search_input = QtWidgets.QLineEdit()
        self._search_input.setPlaceholderText("Buscar por cliente")

        self._clear_filters_button = QtWidgets.QPushButton("Limpar filtros")
        self._clear_filters_button.setMinimumHeight(40)
        self._clear_filters_button.clicked.connect(self._on_clear_filters)

        filters_layout.addWidget(self._date_filter_check, 0, 0)
        filters_layout.addWidget(QtWidgets.QLabel("De"), 0, 1)
        filters_layout.addWidget(self._start_date_input, 0, 2)
        filters_layout.addWidget(QtWidgets.QLabel("Até"), 0, 3)
        filters_layout.addWidget(self._end_date_input, 0, 4)
        filters_layout.addWidget(QtWidgets.QLabel("Tipo"), 1, 0)
        filters_layout.addWidget(self._type_combo, 1, 1, 1, 2)
        filters_layout.addWidget(QtWidgets.QLabel("Cliente"), 1, 3)
        filters_layout.addWidget(self._search_input, 1, 4)
        filters_layout.addWidget(self._clear_filters_button, 1, 5)
        filters_layout.setColumnStretch(6, 1)

        layout.addWidget(filters_group)

        self._documents_table = QtWidgets.QTableWidget(0, 5)
        self._documents_table.setHorizontalHeaderLabels(
            ["Data", "Tipo", "Cliente", "Arquivo", "Ações"]
        )
        self._documents_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self._documents_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._documents_table.horizontalHeader().setStretchLastSection(True)
        self._documents_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents
        )
        self._documents_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents
        )
        self._documents_table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.Stretch
        )
        self._documents_table.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.Stretch
        )
        self._documents_table.verticalHeader().setVisible(False)
        apply_table_theme(
            self._documents_table,
            "dark" if self._services.theme_manager.is_dark() else "light",
        )
        self._services.theme_manager.theme_changed.connect(
            lambda theme, table=self._documents_table: apply_table_theme(table, theme)
        )

        layout.addWidget(self._documents_table)

        self._status_label = QtWidgets.QLabel()
        self._status_label.setStyleSheet("color: #666;")
        layout.addWidget(self._status_label)
        layout.addStretch()

        self._wire_events()

    def _wire_events(self) -> None:
        self._date_filter_check.toggled.connect(self._on_date_filter_toggled)
        self._start_date_input.dateChanged.connect(self._on_filters_changed)
        self._end_date_input.dateChanged.connect(self._on_filters_changed)
        self._type_combo.currentIndexChanged.connect(self._on_filters_changed)
        self._search_input.textChanged.connect(self._on_filters_changed)

    def _on_date_filter_toggled(self, checked: bool) -> None:
        self._start_date_input.setEnabled(checked)
        self._end_date_input.setEnabled(checked)
        self._on_filters_changed()

    def _on_filters_changed(self) -> None:
        if self.isVisible():
            self._filter_timer.start()

    def _on_clear_filters(self) -> None:
        self._date_filter_check.setChecked(False)
        today = QtCore.QDate.currentDate()
        self._start_date_input.setDate(today)
        self._end_date_input.setDate(today)
        self._type_combo.setCurrentIndex(0)
        self._search_input.clear()
        self.refresh()

    def _load_documents(self) -> None:
        doc_type = self._type_combo.currentData()
        start_date = None
        end_date = None
        if self._date_filter_check.isChecked():
            start_date = self._start_date_input.date().toString("yyyy-MM-dd")
            end_date = self._end_date_input.date().toString("yyyy-MM-dd")
        search = self._search_input.text().strip() or None

        self._documents = self._services.document_repo.list_documents(
            doc_type=doc_type,
            start_date=start_date,
            end_date=end_date,
            customer_search=search,
        )
        self._render_documents()

    def _render_documents(self) -> None:
        self._documents_table.setRowCount(0)
        if not self._documents:
            self._status_label.setText("Nenhum documento encontrado.")
            return

        self._status_label.setText(
            f"{len(self._documents)} documento(s) encontrado(s)."
        )
        self._documents_table.setRowCount(len(self._documents))
        for row, document in enumerate(self._documents):
            display_date = document.reference_date or document.created_at
            self._documents_table.setItem(
                row, 0, QtWidgets.QTableWidgetItem(_format_date(display_date))
            )
            self._documents_table.setItem(
                row,
                1,
                QtWidgets.QTableWidgetItem(_document_type_label(document.doc_type)),
            )
            self._documents_table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(document.customer_name)
            )
            self._documents_table.setItem(
                row, 3, QtWidgets.QTableWidgetItem(document.file_name)
            )
            self._documents_table.setCellWidget(row, 4, self._build_actions_cell(document))

    def _build_actions_cell(self, document: Document) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        open_button = QtWidgets.QPushButton("Abrir")
        open_button.clicked.connect(lambda: self._on_open_document(document))
        layout.addWidget(open_button)

        show_button = QtWidgets.QPushButton("Mostrar na pasta")
        show_button.clicked.connect(lambda: self._on_show_in_folder(document))
        layout.addWidget(show_button)

        reexport_button = QtWidgets.QPushButton("Reexportar")
        can_reexport = bool(
            document.order_id
            and document.doc_type in (DocumentType.CONTRACT, DocumentType.RECEIPT)
        )
        reexport_button.setEnabled(can_reexport)
        if can_reexport:
            reexport_button.clicked.connect(lambda: self._on_reexport(document))
        else:
            reexport_button.setToolTip(
                "Reexportação disponível apenas para contratos e recibos vinculados."
            )
        layout.addWidget(reexport_button)
        layout.addStretch()
        return container

    def _on_open_document(self, document: Document) -> None:
        path = Path(document.file_path)
        if not path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Atenção",
                "Arquivo não encontrado. Reexporte o documento para gerar novamente.",
            )
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _on_show_in_folder(self, document: Document) -> None:
        path = Path(document.file_path)
        target = path.parent if path.exists() else Path(document.file_path).parent
        if not target.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Atenção",
                "A pasta do documento não foi encontrada.",
            )
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(target)))

    def _ensure_documents_dir(self) -> Path | None:
        settings = load_documents_settings(self._config_path)
        if settings.documents_dir:
            candidate = Path(settings.documents_dir)
            if candidate.exists():
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate

        selected = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta padrão de documentos",
            str(Path.home()),
        )
        if not selected:
            return None
        chosen_path = Path(selected)
        chosen_path.mkdir(parents=True, exist_ok=True)
        save_documents_settings(
            self._config_path,
            DocumentsSettings(documents_dir=str(chosen_path)),
        )
        return chosen_path

    def _choose_document_path(self, default_path: Path) -> Path | None:
        message = QtWidgets.QMessageBox(self)
        message.setWindowTitle("Salvar documento")
        message.setText("Deseja salvar na pasta padrão ou escolher outro local?")
        default_button = message.addButton(
            "Salvar na pasta padrão", QtWidgets.QMessageBox.AcceptRole
        )
        save_as_button = message.addButton(
            "Salvar como...", QtWidgets.QMessageBox.ActionRole
        )
        message.addButton("Cancelar", QtWidgets.QMessageBox.RejectRole)
        message.exec()

        if message.clickedButton() == default_button:
            return default_path
        if message.clickedButton() == save_as_button:
            selected, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Salvar documento",
                str(default_path),
                "PDF (*.pdf)",
            )
            if not selected:
                return None
            chosen = Path(selected)
            if chosen.suffix.lower() != ".pdf":
                chosen = chosen.with_suffix(".pdf")
            return chosen
        return None

    def _on_reexport(self, document: Document) -> None:
        if not document.order_id:
            return
        try:
            rental_payload = self._build_pdf_payload(document.order_id)
            documents_dir = self._ensure_documents_dir()
            if not documents_dir:
                return
            rental_record, _, customer = rental_payload
            file_name = build_document_filename(
                customer.name,
                rental_record.event_date,
                document.doc_type,
            )
            default_path = documents_dir / file_name
            output_path = self._choose_document_path(default_path)
            if not output_path:
                return
            generate_rental_pdf(
                rental_payload,
                output_path,
                kind=document.doc_type.value,
            )
            created_at = datetime.now().isoformat(timespec="seconds")
            self._services.document_repo.add(
                Document(
                    id=None,
                    created_at=created_at,
                    doc_type=document.doc_type,
                    customer_name=customer.name,
                    reference_date=rental_record.event_date,
                    file_name=output_path.name,
                    file_path=str(output_path),
                    order_id=document.order_id,
                    notes="Reexportado",
                )
            )
            self._services.data_bus.data_changed.emit()
            self._load_documents()
        except Exception:
            self._logger.exception("Falha ao reexportar documento.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível reexportar o documento.",
            )

    def _build_pdf_payload(
        self, rental_id: int
    ) -> tuple[Rental, list[SimpleNamespace], Customer]:
        rental_data = rental_repo.get_rental_with_items(
            rental_id,
            connection=self._services.connection,
        )
        if not rental_data:
            raise RuntimeError("Pedido não encontrado.")
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
                    product_name=product.name if product else f"Item {item.product_id}",
                    qty=item.qty,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
            )
        return rental, items_for_pdf, customer
