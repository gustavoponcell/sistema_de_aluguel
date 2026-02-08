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

from rental_manager.domain.models import Expense, PaymentStatus, RentalStatus
from rental_manager.logging_config import get_logger
from rental_manager.paths import get_exports_dir
from rental_manager.repositories import rental_repo
from rental_manager.services.errors import NotFoundError, ValidationError
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.ui.strings import TERM_ORDER_PLURAL, TITLE_SUCCESS
from rental_manager.ui.widgets import KpiCard
from rental_manager.utils.theme import apply_table_theme


@dataclass(frozen=True)
class SummarySnapshot:
    report: rental_repo.FinanceReport
    rentals: list[rental_repo.RentalFinanceRow]
    monthly_to_receive: list[rental_repo.MonthlyMetric]
    total_expenses: float


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
        self._logger = get_logger(self.__class__.__name__)
        self._rentals: list[rental_repo.RentalFinanceRow] = []
        self._expenses: list[Expense] = []
        self._expense_edit_id: Optional[int] = None
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
            "Acompanhe receitas, pendências e indicadores do período."
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
        self._expenses_tab = QtWidgets.QWidget()
        self._reports_tab = QtWidgets.QWidget()
        self._charts_tab = QtWidgets.QWidget()
        self._tabs.addTab(self._summary_tab, "Resumo")
        self._tabs.addTab(self._expenses_tab, "Despesas")
        self._tabs.addTab(self._reports_tab, "Relatórios")
        self._tabs.addTab(self._charts_tab, "Gráficos")

        self._build_summary_tab()
        self._build_expenses_tab()
        self._build_charts_tab()
        self._build_reports_tab()
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _build_summary_tab(self) -> None:
        summary_layout = QtWidgets.QVBoxLayout(self._summary_tab)

        cards_layout = QtWidgets.QGridLayout()
        cards_layout.setSpacing(12)

        self._received_card = KpiCard(
            self._services.theme_manager, "Total recebido", "R$ 0,00"
        )
        self._to_receive_card = KpiCard(
            self._services.theme_manager, "Total a receber", "R$ 0,00"
        )
        self._expense_card = KpiCard(
            self._services.theme_manager, "Despesas no período", "R$ 0,00"
        )
        self._count_card = KpiCard(
            self._services.theme_manager, f"{TERM_ORDER_PLURAL} no período", "0"
        )
        self._balance_card = KpiCard(
            self._services.theme_manager, "Saldo (Receita - Despesas)", "R$ 0,00"
        )

        cards_layout.addWidget(self._received_card, 0, 0)
        cards_layout.addWidget(self._to_receive_card, 0, 1)
        cards_layout.addWidget(self._expense_card, 0, 2)
        cards_layout.addWidget(self._count_card, 1, 0)
        cards_layout.addWidget(self._balance_card, 1, 1)
        cards_layout.setColumnStretch(2, 1)

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

        receivable_panel = self._create_table_panel("Pendências por mês")
        summary_layout.addWidget(receivable_panel)
        summary_layout.addStretch()

    def _build_expenses_tab(self) -> None:
        expenses_layout = QtWidgets.QVBoxLayout(self._expenses_tab)

        form_group = QtWidgets.QGroupBox("Registrar despesa")
        form_layout = QtWidgets.QFormLayout(form_group)

        self._expense_date = QtWidgets.QDateEdit()
        self._expense_date.setCalendarPopup(True)
        self._expense_date.setDisplayFormat("dd/MM/yyyy")
        self._expense_date.setDate(QtCore.QDate.currentDate())

        self._expense_category = QtWidgets.QComboBox()
        self._expense_category.setEditable(True)

        self._expense_description = QtWidgets.QLineEdit()

        self._expense_amount = QtWidgets.QDoubleSpinBox()
        self._expense_amount.setMaximum(10_000_000)
        self._expense_amount.setDecimals(2)
        self._expense_amount.setPrefix("R$ ")

        self._expense_payment_method = QtWidgets.QLineEdit()
        self._expense_supplier = QtWidgets.QLineEdit()
        self._expense_notes = QtWidgets.QTextEdit()
        self._expense_notes.setFixedHeight(80)

        form_layout.addRow("Data:", self._expense_date)
        form_layout.addRow("Categoria:", self._expense_category)
        form_layout.addRow("Descrição:", self._expense_description)
        form_layout.addRow("Valor:", self._expense_amount)
        form_layout.addRow("Forma de pagamento:", self._expense_payment_method)
        form_layout.addRow("Fornecedor:", self._expense_supplier)
        form_layout.addRow("Observações:", self._expense_notes)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        self._expense_save_button = QtWidgets.QPushButton("Salvar despesa")
        self._expense_save_button.clicked.connect(self._on_expense_save)
        self._expense_clear_button = QtWidgets.QPushButton("Limpar")
        self._expense_clear_button.clicked.connect(self._reset_expense_form)
        buttons_layout.addWidget(self._expense_save_button)
        buttons_layout.addWidget(self._expense_clear_button)
        form_layout.addRow("", buttons_layout)

        expenses_layout.addWidget(form_group)

        table_group = QtWidgets.QGroupBox("Despesas no período")
        table_layout = QtWidgets.QVBoxLayout(table_group)
        self._expense_table = QtWidgets.QTableWidget(0, 8)
        self._expense_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Data",
                "Categoria",
                "Descrição",
                "Valor",
                "Forma",
                "Fornecedor",
                "Observações",
            ]
        )
        self._expense_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._expense_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._expense_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._expense_table.verticalHeader().setVisible(False)
        self._expense_table.setMinimumHeight(260)
        expense_header = self._expense_table.horizontalHeader()
        expense_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        expense_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        expense_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        expense_header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        expense_header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        expense_header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        expense_header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        expense_header.setSectionResizeMode(7, QtWidgets.QHeaderView.Stretch)
        apply_table_theme(
            self._expense_table,
            "dark" if self._services.theme_manager.is_dark() else "light",
        )
        self._services.theme_manager.theme_changed.connect(
            lambda theme, table=self._expense_table: apply_table_theme(table, theme)
        )

        table_layout.addWidget(self._expense_table)

        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.addStretch()
        self._expense_edit_button = QtWidgets.QPushButton("Editar")
        self._expense_edit_button.clicked.connect(self._on_expense_edit)
        self._expense_delete_button = QtWidgets.QPushButton("Excluir")
        self._expense_delete_button.clicked.connect(self._on_expense_delete)
        self._expense_edit_button.setEnabled(False)
        self._expense_delete_button.setEnabled(False)
        actions_layout.addWidget(self._expense_edit_button)
        actions_layout.addWidget(self._expense_delete_button)
        table_layout.addLayout(actions_layout)

        self._expense_table.itemSelectionChanged.connect(
            self._on_expense_selection_changed
        )

        expenses_layout.addWidget(table_group)
        expenses_layout.addStretch()

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
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_content = QtWidgets.QWidget()
        scroll_area.setWidget(scroll_content)
        cards_layout = QtWidgets.QVBoxLayout(scroll_content)
        cards_layout.setSpacing(16)
        cards_layout.setContentsMargins(12, 12, 12, 12)

        cards_layout.addWidget(
            self._create_chart_panel(
                "Receita por mês (últimos 12 meses)",
                "revenue",
            )
        )
        cards_layout.addWidget(
            self._create_chart_panel(
                f"{TERM_ORDER_PLURAL} por mês (últimos 12 meses)",
                "rentals",
            )
        )
        cards_layout.addWidget(
            self._create_chart_panel(
                "Top 10 itens (quantidade)",
                "top_qty",
            )
        )
        cards_layout.addWidget(
            self._create_chart_panel(
                "Top 10 itens (receita)",
                "top_revenue",
            )
        )
        cards_layout.addStretch()

        charts_layout.addWidget(scroll_area)

    def _build_reports_tab(self) -> None:
        reports_layout = QtWidgets.QVBoxLayout(self._reports_tab)

        table_group = QtWidgets.QGroupBox(f"{TERM_ORDER_PLURAL} no período")
        table_layout = QtWidgets.QVBoxLayout(table_group)
        self._table = QtWidgets.QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            [
                "ID",
                "Cliente",
                "Data do pedido",
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
        self._table.setMinimumHeight(260)
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
        apply_table_theme(
            self._table, "dark" if self._services.theme_manager.is_dark() else "light"
        )
        self._services.theme_manager.theme_changed.connect(
            lambda theme, table=self._table: apply_table_theme(table, theme)
        )

        table_layout.addWidget(self._table)
        reports_layout.addWidget(table_group)

        expenses_group = QtWidgets.QGroupBox("Despesas no período")
        expenses_layout = QtWidgets.QVBoxLayout(expenses_group)
        self._expenses_report_table = QtWidgets.QTableWidget(0, 8)
        self._expenses_report_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Data",
                "Categoria",
                "Descrição",
                "Valor",
                "Forma",
                "Fornecedor",
                "Observações",
            ]
        )
        self._expenses_report_table.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )
        self._expenses_report_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self._expenses_report_table.verticalHeader().setVisible(False)
        self._expenses_report_table.setMinimumHeight(260)
        expenses_header = self._expenses_report_table.horizontalHeader()
        expenses_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        expenses_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        expenses_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        expenses_header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        expenses_header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        expenses_header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        expenses_header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        expenses_header.setSectionResizeMode(7, QtWidgets.QHeaderView.Stretch)
        apply_table_theme(
            self._expenses_report_table,
            "dark" if self._services.theme_manager.is_dark() else "light",
        )
        self._services.theme_manager.theme_changed.connect(
            lambda theme, table=self._expenses_report_table: apply_table_theme(
                table, theme
            )
        )
        expenses_layout.addWidget(self._expenses_report_table)
        reports_layout.addWidget(expenses_group)

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

    def _create_chart_panel(self, title: str, key: str) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setFrameShape(QtWidgets.QFrame.StyledPanel)
        card.setFrameShadow(QtWidgets.QFrame.Raised)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        card_layout.addWidget(title_label)

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
            figure = Figure(figsize=(10, 4))
            canvas = FigureCanvas(figure)
            canvas.setMinimumHeight(340)
            canvas.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
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
            chart_view.setMinimumHeight(340)
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

        card_layout.addLayout(stack)
        self._chart_panels[key] = panel
        return card

    def _create_table_panel(self, title: str) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(group)

        self._receivable_table = QtWidgets.QTableWidget(0, 2)
        self._receivable_table.setHorizontalHeaderLabels(["Mês", "Pendência"])
        self._receivable_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._receivable_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._receivable_table.verticalHeader().setVisible(False)
        table_header = self._receivable_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        table_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        apply_table_theme(
            self._receivable_table,
            "dark" if self._services.theme_manager.is_dark() else "light",
        )
        self._services.theme_manager.theme_changed.connect(
            lambda theme, table=self._receivable_table: apply_table_theme(table, theme)
        )

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
        self._expense_card.set_value(_format_currency(snapshot.total_expenses))
        self._count_card.set_value(str(snapshot.report.rentals_count))
        balance = snapshot.report.total_received - snapshot.total_expenses
        self._balance_card.set_value(_format_currency(balance))

        self._populate_table(self._rentals)
        _, months, _ = self._chart_months(end_date)
        receivable_values = self._month_values(months, snapshot.monthly_to_receive)
        self._populate_receivable_table(months, receivable_values)
        self._load_expenses_data(start_date, end_date)
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
        chart_start_date, _, _ = self._chart_months(end_date)
        monthly_to_receive = rental_repo.list_monthly_to_receive(
            chart_start_date, end_date, connection=self._services.connection
        )
        total_expenses = self._services.expense_service.get_total_by_period(
            start_date, end_date
        )
        return SummarySnapshot(
            report=report,
            rentals=rentals,
            monthly_to_receive=monthly_to_receive,
            total_expenses=total_expenses,
        )

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

    def _load_expenses_data(self, start_date: str, end_date: str) -> None:
        try:
            self._expenses = self._services.expense_service.list_expenses(
                start_date, end_date
            )
        except Exception:
            self._logger.exception("Falha ao carregar despesas.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível carregar as despesas do período.",
            )
            self._expenses = []
        self._populate_expenses_table(self._expense_table, self._expenses)
        self._populate_expenses_table(self._expenses_report_table, self._expenses)
        self._refresh_expense_categories()

    def _populate_expenses_table(
        self,
        table: QtWidgets.QTableWidget,
        expenses: Iterable[Expense],
    ) -> None:
        table.setRowCount(0)
        for row_index, expense in enumerate(expenses):
            table.insertRow(row_index)
            table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(str(expense.id)))
            table.setItem(
                row_index, 1, QtWidgets.QTableWidgetItem(_format_date(expense.date))
            )
            table.setItem(
                row_index,
                2,
                QtWidgets.QTableWidgetItem(expense.category or "—"),
            )
            table.setItem(
                row_index,
                3,
                QtWidgets.QTableWidgetItem(expense.description or "—"),
            )
            table.setItem(
                row_index,
                4,
                QtWidgets.QTableWidgetItem(_format_currency(expense.amount)),
            )
            table.setItem(
                row_index,
                5,
                QtWidgets.QTableWidgetItem(expense.payment_method or "—"),
            )
            table.setItem(
                row_index,
                6,
                QtWidgets.QTableWidgetItem(expense.supplier or "—"),
            )
            table.setItem(
                row_index,
                7,
                QtWidgets.QTableWidgetItem(expense.notes or "—"),
            )
        table.resizeRowsToContents()
        if table is self._expense_table:
            table.clearSelection()
            self._on_expense_selection_changed()

    def _refresh_expense_categories(self) -> None:
        try:
            categories = self._services.expense_service.list_categories()
        except Exception:
            self._logger.exception("Falha ao carregar categorias de despesas.")
            categories = []
        current = self._expense_category.currentText()
        self._expense_category.blockSignals(True)
        self._expense_category.clear()
        self._expense_category.addItems(categories)
        if current:
            self._expense_category.setCurrentText(current)
        self._expense_category.blockSignals(False)

    def _on_expense_selection_changed(self) -> None:
        has_selection = self._selected_expense() is not None
        self._expense_edit_button.setEnabled(has_selection)
        self._expense_delete_button.setEnabled(has_selection)

    def _selected_expense(self) -> Optional[Expense]:
        selected = self._expense_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self._expenses):
            return None
        return self._expenses[row]

    def _reset_expense_form(self) -> None:
        self._expense_edit_id = None
        self._expense_date.setDate(QtCore.QDate.currentDate())
        self._expense_category.setCurrentText("")
        self._expense_description.clear()
        self._expense_amount.setValue(0.0)
        self._expense_payment_method.clear()
        self._expense_supplier.clear()
        self._expense_notes.clear()
        self._expense_save_button.setText("Salvar despesa")

    def _on_expense_edit(self) -> None:
        expense = self._selected_expense()
        if not expense:
            return
        parsed_date = QtCore.QDate.fromString(expense.date, "yyyy-MM-dd")
        if parsed_date.isValid():
            self._expense_date.setDate(parsed_date)
        self._expense_category.setCurrentText(expense.category or "")
        self._expense_description.setText(expense.description or "")
        self._expense_amount.setValue(float(expense.amount))
        self._expense_payment_method.setText(expense.payment_method or "")
        self._expense_supplier.setText(expense.supplier or "")
        self._expense_notes.setPlainText(expense.notes or "")
        self._expense_edit_id = expense.id
        self._expense_save_button.setText("Atualizar despesa")

    def _on_expense_save(self) -> None:
        date = self._expense_date.date().toString("yyyy-MM-dd")
        category = self._expense_category.currentText().strip() or None
        description = self._expense_description.text().strip() or None
        amount = float(self._expense_amount.value())
        payment_method = self._expense_payment_method.text().strip() or None
        supplier = self._expense_supplier.text().strip() or None
        notes = self._expense_notes.toPlainText().strip() or None

        try:
            if self._expense_edit_id:
                self._services.expense_service.update_expense(
                    expense_id=self._expense_edit_id,
                    date=date,
                    category=category,
                    description=description,
                    amount=amount,
                    payment_method=payment_method,
                    supplier=supplier,
                    notes=notes,
                )
            else:
                self._services.expense_service.create_expense(
                    date=date,
                    category=category,
                    description=description,
                    amount=amount,
                    payment_method=payment_method,
                    supplier=supplier,
                    notes=notes,
                )
        except ValidationError as error:
            self._logger.warning("Validação de despesa: %s", error)
            QtWidgets.QMessageBox.warning(self, "Atenção", str(error))
            return
        except NotFoundError as error:
            self._logger.warning("Despesa não encontrada: %s", error)
            QtWidgets.QMessageBox.warning(self, "Atenção", str(error))
            return
        except Exception:
            self._logger.exception("Falha ao salvar despesa.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível salvar a despesa. Tente novamente.",
            )
            return

        self._services.data_bus.data_changed.emit()
        self._reset_expense_form()

    def _on_expense_delete(self) -> None:
        expense = self._selected_expense()
        if not expense:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirmação",
            "Deseja realmente excluir esta despesa?",
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            self._services.expense_service.delete_expense(expense.id or 0)
        except NotFoundError as error:
            self._logger.warning("Despesa não encontrada ao excluir: %s", error)
            QtWidgets.QMessageBox.warning(self, "Atenção", str(error))
            return
        except Exception:
            self._logger.exception("Falha ao excluir despesa.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível excluir a despesa. Tente novamente.",
            )
            return
        self._services.data_bus.data_changed.emit()

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
            "Data do pedido",
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
            TITLE_SUCCESS,
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


def _format_date(value: Optional[str]) -> str:
    if not value:
        return "—"
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
