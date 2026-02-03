"""Screen for finance overview."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

try:  # Matplotlib preferred
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter

    _MATPLOTLIB_AVAILABLE = True
except Exception:
    FigureCanvas = None
    Figure = None
    FuncFormatter = None
    _MATPLOTLIB_AVAILABLE = False

try:  # QtCharts fallback
    from PySide6.QtCharts import (
        QBarCategoryAxis,
        QBarSeries,
        QBarSet,
        QChart,
        QChartView,
        QValueAxis,
    )

    _QTCHARTS_AVAILABLE = True
except Exception:
    _QTCHARTS_AVAILABLE = False

from dateutil.relativedelta import relativedelta

from rental_manager.domain.models import PaymentStatus, RentalStatus
from rental_manager.paths import get_exports_dir
from rental_manager.repositories import rental_repo
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.ui.widgets import KpiCard


@dataclass(frozen=True)
class SummarySnapshot:
    report: rental_repo.FinanceReport
    rentals: list[rental_repo.RentalFinanceRow]


@dataclass(frozen=True)
class ChartsSnapshot:
    monthly_revenue: list[rental_repo.MonthlyMetric]
    monthly_rentals: list[rental_repo.MonthlyMetric]
    monthly_to_receive: list[rental_repo.MonthlyMetric]
    top_qty: list[rental_repo.RankedMetric]
    top_revenue: Optional[list[rental_repo.RankedMetric]]


class FinanceScreen(BaseScreen):
    """Screen for finance reports."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._rentals: list[rental_repo.RentalFinanceRow] = []
        self._summary_cache: dict[tuple[str, str], SummarySnapshot] = {}
        self._charts_cache: dict[tuple[str, str], ChartsSnapshot] = {}
        self._chart_backend = self._resolve_chart_backend()
        self._chart_panels: dict[str, dict[str, object]] = {}
        self._charts_loaded = False
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.timeout.connect(self.refresh)
        self._build_ui()
        self._load_data()

    def _resolve_chart_backend(self) -> str:
        if _MATPLOTLIB_AVAILABLE:
            return "matplotlib"
        if _QTCHARTS_AVAILABLE:
            return "qtcharts"
        return "none"

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
        start_period = today.addMonths(-11)
        start_period = QtCore.QDate(start_period.year(), start_period.month(), 1)
        self._start_date.setDate(start_period)
        self._end_date.setDate(today)

        self._refresh_button = QtWidgets.QPushButton("Atualizar")
        self._refresh_button.clicked.connect(self._on_refresh_clicked)
        self._start_date.dateChanged.connect(self._on_filters_changed)
        self._end_date.dateChanged.connect(self._on_filters_changed)

        filter_layout.addWidget(QtWidgets.QLabel("Início:"))
        filter_layout.addWidget(self._start_date)
        filter_layout.addWidget(QtWidgets.QLabel("Fim:"))
        filter_layout.addWidget(self._end_date)
        filter_layout.addStretch()
        filter_layout.addWidget(self._refresh_button)

        layout.addWidget(filter_group)

        self._tabs = QtWidgets.QTabWidget()
        layout.addWidget(self._tabs)

        self._summary_tab = QtWidgets.QWidget()
        self._charts_tab = QtWidgets.QWidget()
        self._reports_tab = QtWidgets.QWidget()
        self._tabs.addTab(self._summary_tab, "Resumo")
        self._tabs.addTab(self._charts_tab, "Gráficos")
        self._tabs.addTab(self._reports_tab, "Relatórios")

        self._build_summary_tab()
        self._build_charts_tab()
        self._build_reports_tab()
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _build_summary_tab(self) -> None:
        summary_layout = QtWidgets.QVBoxLayout(self._summary_tab)

        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(12)

        self._received_card = KpiCard(
            self._services.theme_manager, "Total recebido", "R$ 0,00"
        )
        self._to_receive_card = KpiCard(
            self._services.theme_manager, "Total a receber", "R$ 0,00"
        )
        self._count_card = KpiCard(
            self._services.theme_manager, "Aluguéis no período", "0"
        )

        cards_layout.addWidget(self._received_card)
        cards_layout.addWidget(self._to_receive_card)
        cards_layout.addWidget(self._count_card)

        summary_layout.addLayout(cards_layout)

        self._charts_notice = QtWidgets.QLabel()
        self._charts_notice.setWordWrap(True)
        self._charts_notice.setVisible(False)
        summary_layout.addWidget(self._charts_notice)

        if self._chart_backend == "none":
            self._charts_notice.setText(
                "Gráficos indisponíveis: não foi possível carregar Matplotlib ou "
                "QtCharts. Os KPIs e tabelas continuam disponíveis."
            )
            self._charts_notice.setVisible(True)

        summary_layout.addStretch()

    def _build_charts_tab(self) -> None:
        charts_layout = QtWidgets.QVBoxLayout(self._charts_tab)

        charts_notice = QtWidgets.QLabel()
        charts_notice.setWordWrap(True)
        charts_notice.setVisible(False)
        charts_layout.addWidget(charts_notice)

        if self._chart_backend == "none":
            charts_notice.setText(
                "Gráficos indisponíveis: não foi possível carregar Matplotlib ou "
                "QtCharts. Os relatórios continuam disponíveis."
            )
            charts_notice.setVisible(True)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_area.setWidget(scroll_content)
        grid_layout = QtWidgets.QGridLayout(scroll_content)
        grid_layout.setSpacing(12)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)

        revenue_panel = self._create_chart_panel(
            "Receita prevista por mês (últimos 12 meses)",
            "revenue",
        )
        rentals_panel = self._create_chart_panel(
            "Aluguéis por mês (últimos 12 meses)",
            "rentals",
        )
        top_qty_panel = self._create_chart_panel(
            "Top 10 produtos (quantidade)",
            "top_qty",
        )
        top_revenue_panel = self._create_chart_panel(
            "Top 10 produtos (receita)",
            "top_revenue",
        )
        receivable_panel = self._create_table_panel("A receber por mês")

        grid_layout.addWidget(revenue_panel, 0, 0)
        grid_layout.addWidget(rentals_panel, 0, 1)
        grid_layout.addWidget(top_qty_panel, 1, 0)
        grid_layout.addWidget(top_revenue_panel, 1, 1)
        grid_layout.addWidget(receivable_panel, 2, 0, 1, 2)

        charts_layout.addWidget(scroll_area)
        charts_layout.addStretch()

    def _build_reports_tab(self) -> None:
        reports_layout = QtWidgets.QVBoxLayout(self._reports_tab)

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
        reports_layout.addWidget(table_group)

        export_layout = QtWidgets.QHBoxLayout()
        export_layout.addStretch()
        export_button = QtWidgets.QPushButton("Exportar CSV")
        export_button.clicked.connect(self._export_csv)
        export_layout.addWidget(export_button)
        reports_layout.addLayout(export_layout)

        reports_layout.addStretch()

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.widget(index) is not self._charts_tab:
            return
        if self._charts_loaded:
            return
        self._charts_loaded = True
        start_date, end_date = self._current_period()
        self._load_charts_data(start_date, end_date, force=False)

    def _create_chart_panel(self, title: str, key: str) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(group)

        stack = QtWidgets.QStackedLayout()
        empty_label = QtWidgets.QLabel("Sem dados")
        empty_label.setAlignment(QtCore.Qt.AlignCenter)
        empty_label.setWordWrap(True)

        panel: dict[str, object] = {
            "stack": stack,
            "label": empty_label,
            "backend": self._chart_backend,
        }

        if self._chart_backend == "matplotlib" and FigureCanvas and Figure:
            figure = Figure(figsize=(5, 3))
            canvas = FigureCanvas(figure)
            axis = figure.add_subplot(111)
            stack.addWidget(canvas)
            stack.addWidget(empty_label)
            panel.update(
                {
                    "figure": figure,
                    "canvas": canvas,
                    "axis": axis,
                    "chart_widget": canvas,
                }
            )
        elif self._chart_backend == "qtcharts":
            chart = QChart()
            chart.setAnimationOptions(QChart.SeriesAnimations)
            chart_view = QChartView(chart)
            chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
            stack.addWidget(chart_view)
            stack.addWidget(empty_label)
            panel.update(
                {
                    "chart": chart,
                    "chart_view": chart_view,
                    "chart_widget": chart_view,
                }
            )
        else:
            empty_label.setText(
                "Gráfico indisponível: Matplotlib/QtCharts não está acessível."
            )
            stack.addWidget(empty_label)

        layout.addLayout(stack)
        self._chart_panels[key] = panel
        return group

    def _create_table_panel(self, title: str) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(group)

        self._receivable_table = QtWidgets.QTableWidget(0, 2)
        self._receivable_table.setHorizontalHeaderLabels(["Mês", "A receber"])
        self._receivable_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._receivable_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._receivable_table.verticalHeader().setVisible(False)
        table_header = self._receivable_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        table_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)

        empty_label = QtWidgets.QLabel("Sem dados")
        empty_label.setAlignment(QtCore.Qt.AlignCenter)
        empty_label.setWordWrap(True)

        stack = QtWidgets.QStackedLayout()
        stack.addWidget(self._receivable_table)
        stack.addWidget(empty_label)
        layout.addLayout(stack)

        self._receivable_panel = {
            "stack": stack,
            "label": empty_label,
        }

        return group

    def _load_data(self, *, force: bool = False) -> None:
        start_date, end_date = self._current_period()
        cache_key = (start_date, end_date)
        if force or cache_key not in self._summary_cache:
            snapshot = self._fetch_summary_data(start_date, end_date)
            self._summary_cache[cache_key] = snapshot
        else:
            snapshot = self._summary_cache[cache_key]

        self._rentals = snapshot.rentals
        self._received_card.set_value(_format_currency(snapshot.report.total_received))
        self._to_receive_card.set_value(_format_currency(snapshot.report.total_to_receive))
        self._count_card.set_value(str(snapshot.report.rentals_count))

        self._populate_table(self._rentals)
        if self._charts_loaded:
            self._load_charts_data(start_date, end_date, force=force)

    def _fetch_summary_data(
        self,
        start_date: str,
        end_date: str,
    ) -> SummarySnapshot:
        report = rental_repo.get_finance_report_by_period(
            start_date, end_date, connection=self._services.connection
        )
        rentals = rental_repo.list_rentals_by_period(
            start_date, end_date, connection=self._services.connection
        )
        return SummarySnapshot(report=report, rentals=rentals)

    def _load_charts_data(
        self, start_date: str, end_date: str, *, force: bool
    ) -> None:
        if self._chart_backend == "none":
            return
        cache_key = (start_date, end_date)
        if force or cache_key not in self._charts_cache:
            snapshot = self._fetch_charts_data(start_date, end_date)
            self._charts_cache[cache_key] = snapshot
        else:
            snapshot = self._charts_cache[cache_key]
        self._update_dashboard_charts(snapshot, end_date=end_date)

    def _fetch_charts_data(self, start_date: str, end_date: str) -> ChartsSnapshot:
        chart_start_date, _, _ = self._chart_months(end_date)
        monthly_revenue = rental_repo.list_monthly_revenue(
            chart_start_date, end_date, connection=self._services.connection
        )
        monthly_rentals = rental_repo.list_monthly_rentals(
            chart_start_date, end_date, connection=self._services.connection
        )
        monthly_to_receive = rental_repo.list_monthly_to_receive(
            chart_start_date, end_date, connection=self._services.connection
        )
        top_qty = rental_repo.list_top_products_by_qty(
            start_date, end_date, connection=self._services.connection
        )
        top_revenue = rental_repo.list_top_products_by_revenue(
            start_date, end_date, connection=self._services.connection
        )
        return ChartsSnapshot(
            monthly_revenue=monthly_revenue,
            monthly_rentals=monthly_rentals,
            monthly_to_receive=monthly_to_receive,
            top_qty=top_qty,
            top_revenue=top_revenue,
        )

    def _chart_months(self, end_date: str) -> tuple[str, list[str], list[str]]:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        end_month = end_dt.replace(day=1)
        start_month = end_month - relativedelta(months=11)
        months: list[str] = []
        labels: list[str] = []
        current = start_month
        for _ in range(12):
            months.append(current.strftime("%Y-%m"))
            labels.append(current.strftime("%m/%y"))
            current = current + relativedelta(months=1)
        return start_month.strftime("%Y-%m-%d"), months, labels

    def _month_values(
        self,
        months: list[str],
        metrics: Iterable[rental_repo.MonthlyMetric],
    ) -> list[float]:
        mapping = {metric.month: metric.value for metric in metrics}
        return [float(mapping.get(month, 0.0)) for month in months]

    def _update_dashboard_charts(
        self,
        snapshot: ChartsSnapshot,
        *,
        end_date: str,
    ) -> None:
        _, months, labels = self._chart_months(end_date)
        revenue_values = self._month_values(months, snapshot.monthly_revenue)
        rental_values = self._month_values(months, snapshot.monthly_rentals)
        receivable_values = self._month_values(months, snapshot.monthly_to_receive)

        self._update_chart(
            "revenue",
            labels,
            revenue_values,
            currency=True,
        )
        self._update_chart("rentals", labels, rental_values, currency=False)

        top_qty_labels = [self._short_label(item.label) for item in snapshot.top_qty]
        top_qty_values = [item.value for item in snapshot.top_qty]
        self._update_chart("top_qty", top_qty_labels, top_qty_values, currency=False)

        if snapshot.top_revenue is None:
            self._show_chart_message(
                "top_revenue",
                "Cadastre preço por produto para ver a receita por item.",
            )
        else:
            top_revenue_labels = [
                self._short_label(item.label) for item in snapshot.top_revenue
            ]
            top_revenue_values = [item.value for item in snapshot.top_revenue]
            self._update_chart(
                "top_revenue",
                top_revenue_labels,
                top_revenue_values,
                currency=True,
            )

        self._populate_receivable_table(months, receivable_values)

    def _populate_receivable_table(
        self,
        months: list[str],
        values: list[float],
    ) -> None:
        self._receivable_table.setRowCount(0)
        if not values or all(value <= 0 for value in values):
            self._receivable_panel["label"].setText("Sem dados")
            self._receivable_panel["stack"].setCurrentWidget(
                self._receivable_panel["label"]
            )
            return

        for month, value in zip(months, values):
            if value <= 0:
                continue
            row_index = self._receivable_table.rowCount()
            self._receivable_table.insertRow(row_index)
            self._receivable_table.setItem(
                row_index, 0, QtWidgets.QTableWidgetItem(_format_month(month))
            )
            self._receivable_table.setItem(
                row_index, 1, QtWidgets.QTableWidgetItem(_format_currency(value))
            )
        self._receivable_table.resizeRowsToContents()
        self._receivable_panel["stack"].setCurrentWidget(self._receivable_table)

    def _show_chart_message(self, key: str, message: str) -> None:
        panel = self._chart_panels.get(key)
        if not panel:
            return
        label: QtWidgets.QLabel = panel["label"]  # type: ignore[assignment]
        label.setText(message)
        stack: QtWidgets.QStackedLayout = panel["stack"]  # type: ignore[assignment]
        stack.setCurrentWidget(label)

    def _show_chart(self, key: str) -> None:
        panel = self._chart_panels.get(key)
        if not panel:
            return
        chart_widget = panel.get("chart_widget")
        if not chart_widget:
            return
        stack: QtWidgets.QStackedLayout = panel["stack"]  # type: ignore[assignment]
        stack.setCurrentWidget(chart_widget)

    def _update_chart(
        self,
        key: str,
        labels: list[str],
        values: list[float],
        *,
        currency: bool,
    ) -> None:
        if self._chart_backend == "none":
            return
        if not values or all(value == 0 for value in values):
            panel = self._chart_panels.get(key)
            if panel and panel["backend"] == "matplotlib":
                axis = panel["axis"]
                figure = panel["figure"]
                canvas = panel["canvas"]
                axis.clear()
                figure.tight_layout()
                canvas.draw()
            if panel and panel["backend"] == "qtcharts":
                chart: QChart = panel["chart"]  # type: ignore[assignment]
                chart.removeAllSeries()
            self._show_chart_message(key, "Sem dados")
            return
        panel = self._chart_panels.get(key)
        if not panel:
            return
        if panel["backend"] == "matplotlib":
            axis = panel["axis"]
            figure = panel["figure"]
            canvas = panel["canvas"]
            axis.clear()
            axis.bar(range(len(values)), values, color="#4C78A8")
            axis.set_xticks(range(len(labels)))
            axis.set_xticklabels(labels, rotation=45, ha="right")
            axis.set_ylim(bottom=0)
            if currency and FuncFormatter:
                axis.yaxis.set_major_formatter(
                    FuncFormatter(lambda value, _: _format_currency(value))
                )
            figure.tight_layout()
            canvas.draw()
            self._show_chart(key)
        elif panel["backend"] == "qtcharts":
            chart: QChart = panel["chart"]  # type: ignore[assignment]
            chart.removeAllSeries()
            bar_set = QBarSet("")
            bar_set.append(values)
            series = QBarSeries()
            series.append(bar_set)
            chart.addSeries(series)
            axis_x = QBarCategoryAxis()
            axis_x.append(labels)
            axis_y = QValueAxis()
            axis_y.setMin(0)
            axis_y.setMax(max(values) * 1.2 if max(values) > 0 else 1)
            chart.setAxisX(axis_x, series)
            chart.setAxisY(axis_y, series)
            chart.legend().setVisible(False)
            self._show_chart(key)

    def _short_label(self, label: str) -> str:
        return label if len(label) <= 18 else f"{label[:15]}…"

    def _on_filters_changed(self) -> None:
        self._refresh_timer.start()

    def _on_refresh_clicked(self) -> None:
        self._load_data(force=True)

    def refresh(self) -> None:
        self._load_data()

    def _on_data_changed(self) -> None:
        self._summary_cache.clear()
        self._charts_cache.clear()
        super()._on_data_changed()

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


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_date(value: str) -> str:
    parsed = QtCore.QDate.fromString(value, "yyyy-MM-dd")
    return parsed.toString("dd/MM/yyyy") if parsed.isValid() else value


def _format_month(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m")
    return parsed.strftime("%m/%Y")


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
