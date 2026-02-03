"""Screen for finance overview."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PySide6 import QtCore, QtWidgets

from rental_manager.domain.models import PaymentStatus, RentalStatus
from rental_manager.paths import get_config_path, get_exports_dir
from rental_manager.repositories import rental_repo
from rental_manager.utils.theme import load_theme_settings, resolve_theme_choice

from rental_manager.ui.app_services import AppServices


class FinanceScreen(QtWidgets.QWidget):
    """Screen for finance reports."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._rentals: list[rental_repo.RentalFinanceRow] = []
        self._cards_container: QtWidgets.QWidget | None = None
        self._build_ui()
        self.apply_kpi_card_style()
        self._load_data()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Financeiro")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Acompanhe valores recebidos, pendências e relatórios simples."
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        filter_group = QtWidgets.QGroupBox("Período")
        filter_layout = QtWidgets.QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(12, 8, 12, 8)

        self._start_date = QtWidgets.QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDisplayFormat("dd/MM/yyyy")

        self._end_date = QtWidgets.QDateEdit()
        self._end_date.setCalendarPopup(True)
        self._end_date.setDisplayFormat("dd/MM/yyyy")

        today = QtCore.QDate.currentDate()
        start_of_month = QtCore.QDate(today.year(), today.month(), 1)
        self._start_date.setDate(start_of_month)
        self._end_date.setDate(today)

        refresh_button = QtWidgets.QPushButton("Atualizar")
        refresh_button.clicked.connect(self._load_data)

        filter_layout.addWidget(QtWidgets.QLabel("Início:"))
        filter_layout.addWidget(self._start_date)
        filter_layout.addWidget(QtWidgets.QLabel("Fim:"))
        filter_layout.addWidget(self._end_date)
        filter_layout.addStretch()
        filter_layout.addWidget(refresh_button)

        layout.addWidget(filter_group)

        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(12)

        self._received_card = self._create_summary_card("Total recebido", "R$ 0,00")
        self._to_receive_card = self._create_summary_card("Total a receber", "R$ 0,00")
        self._count_card = self._create_summary_card("Aluguéis no período", "0")

        cards_layout.addWidget(self._received_card.container)
        cards_layout.addWidget(self._to_receive_card.container)
        cards_layout.addWidget(self._count_card.container)

        self._cards_container = QtWidgets.QWidget()
        self._cards_container.setLayout(cards_layout)
        layout.addWidget(self._cards_container)

        table_group = QtWidgets.QGroupBox("Aluguéis no período")
        table_layout = QtWidgets.QVBoxLayout(table_group)
        self._table = QtWidgets.QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            [
                "ID",
                "Cliente",
                "Evento",
                "Início",
                "Fim",
                "Status",
                "Pagamento",
                "Total",
                "Pago",
            ]
        )
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeToContents)

        table_layout.addWidget(self._table)
        layout.addWidget(table_group)

        export_layout = QtWidgets.QHBoxLayout()
        export_layout.addStretch()
        export_button = QtWidgets.QPushButton("Exportar CSV")
        export_button.clicked.connect(self._export_csv)
        export_layout.addWidget(export_button)
        layout.addLayout(export_layout)

        layout.addStretch()

    def _create_summary_card(self, title: str, value: str) -> "_SummaryCard":
        container = QtWidgets.QFrame()
        container.setObjectName("KpiCard")
        container.setFrameShape(QtWidgets.QFrame.StyledPanel)
        card_layout = QtWidgets.QVBoxLayout(container)
        card_layout.setContentsMargins(16, 12, 16, 12)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("KpiTitle")
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("KpiValue")
        value_label.setEnabled(True)

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)

        return _SummaryCard(container=container, value_label=value_label)

    def apply_kpi_card_style(self) -> None:
        settings = load_theme_settings(get_config_path())
        theme_name = resolve_theme_choice(settings.theme)
        if theme_name == "dark":
            stylesheet = """
            QFrame#KpiCard {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 10px;
            }
            QLabel#KpiTitle {
                color: rgba(255, 255, 255, 0.78);
            }
            QLabel#KpiValue {
                color: rgba(255, 255, 255, 0.95);
                font-size: 22px;
                font-weight: 700;
            }
            """
        else:
            stylesheet = """
            QFrame#KpiCard {
                background-color: #ffffff;
                border: 1px solid rgba(0, 0, 0, 0.10);
                border-radius: 10px;
            }
            QLabel#KpiTitle {
                color: rgba(0, 0, 0, 0.70);
            }
            QLabel#KpiValue {
                color: rgba(0, 0, 0, 0.92);
                font-size: 22px;
                font-weight: 700;
            }
            """
        if self._cards_container is not None:
            self._cards_container.setStyleSheet(stylesheet)

    def _load_data(self) -> None:
        start_date, end_date = self._current_period()
        report = rental_repo.get_finance_report_by_period(
            start_date, end_date, connection=self._services.connection
        )
        self._rentals = rental_repo.list_rentals_by_period(
            start_date, end_date, connection=self._services.connection
        )

        self._received_card.value_label.setText(_format_currency(report.total_received))
        self._to_receive_card.value_label.setText(
            _format_currency(report.total_to_receive)
        )
        self._count_card.value_label.setText(str(report.rentals_count))

        self._populate_table(self._rentals)
        self.apply_kpi_card_style()

    def _current_period(self) -> tuple[str, str]:
        start_qdate = self._start_date.date()
        end_qdate = self._end_date.date()
        if start_qdate > end_qdate:
            end_qdate = start_qdate
            self._end_date.setDate(end_qdate)
        start_date = start_qdate.toString("yyyy-MM-dd")
        end_date = end_qdate.toString("yyyy-MM-dd")
        return start_date, end_date

    def _populate_table(
        self, rentals: Iterable[rental_repo.RentalFinanceRow]
    ) -> None:
        self._table.setRowCount(0)
        for row_index, rental in enumerate(rentals):
            self._table.insertRow(row_index)
            self._table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(str(rental.id)))
            self._table.setItem(
                row_index, 1, QtWidgets.QTableWidgetItem(rental.customer_name)
            )
            self._table.setItem(
                row_index, 2, QtWidgets.QTableWidgetItem(_format_date(rental.event_date))
            )
            self._table.setItem(
                row_index, 3, QtWidgets.QTableWidgetItem(_format_date(rental.start_date))
            )
            self._table.setItem(
                row_index, 4, QtWidgets.QTableWidgetItem(_format_date(rental.end_date))
            )
            self._table.setItem(
                row_index, 5, QtWidgets.QTableWidgetItem(_status_label(rental.status))
            )
            self._table.setItem(
                row_index,
                6,
                QtWidgets.QTableWidgetItem(_payment_label(rental.payment_status)),
            )
            self._table.setItem(
                row_index,
                7,
                QtWidgets.QTableWidgetItem(_format_currency(rental.total_value)),
            )
            self._table.setItem(
                row_index,
                8,
                QtWidgets.QTableWidgetItem(_format_currency(rental.paid_value)),
            )
        self._table.resizeRowsToContents()

    def _export_csv(self) -> None:
        exports_dir = get_exports_dir()
        start_date, end_date = self._current_period()
        self._rentals = rental_repo.list_rentals_by_period(
            start_date, end_date, connection=self._services.connection
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"financeiro_{start_date}_a_{end_date}_{timestamp}.csv"
        filepath = exports_dir / filename

        headers = [
            "ID",
            "Cliente",
            "Evento",
            "Início",
            "Fim",
            "Status",
            "Pagamento",
            "Total",
            "Pago",
            "Em aberto",
        ]
        rows = [self._csv_row(rental) for rental in self._rentals]
        self._write_csv(filepath, headers, rows)

        QtWidgets.QMessageBox.information(
            self,
            "Exportação concluída",
            f"Arquivo salvo em:\n{filepath}",
        )

    def _csv_row(self, rental: rental_repo.RentalFinanceRow) -> list[str]:
        open_value = max(rental.total_value - rental.paid_value, 0)
        return [
            str(rental.id),
            rental.customer_name,
            rental.event_date,
            rental.start_date,
            rental.end_date,
            _status_label(rental.status),
            _payment_label(rental.payment_status),
            f"{rental.total_value:.2f}",
            f"{rental.paid_value:.2f}",
            f"{open_value:.2f}",
        ]

    def _write_csv(
        self, filepath: Path, headers: list[str], rows: Iterable[list[str]]
    ) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with filepath.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(headers)
            writer.writerows(rows)


@dataclass(frozen=True)
class _SummaryCard:
    container: QtWidgets.QFrame
    value_label: QtWidgets.QLabel


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_date(value: str) -> str:
    parsed = QtCore.QDate.fromString(value, "yyyy-MM-dd")
    return parsed.toString("dd/MM/yyyy") if parsed.isValid() else value


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
