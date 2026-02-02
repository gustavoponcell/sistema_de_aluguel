"""Main window for the RentalManager application."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens import (
    BackupScreen,
    CustomersScreen,
    FinanceScreen,
    NewRentalScreen,
    ProductsScreen,
    RentalsScreen,
)


class MainWindow(QtWidgets.QMainWindow):
    """Primary window with navigation and stacked screens."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._stack = QtWidgets.QStackedWidget()
        self.setWindowTitle("RentalManager")
        self.resize(1024, 640)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)

        title = QtWidgets.QLabel("RentalManager")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        title.setAlignment(QtCore.Qt.AlignLeft)

        sidebar_layout.addWidget(title)

        button_group = QtWidgets.QButtonGroup(self)
        button_group.setExclusive(True)

        screens = [
            ("Novo Aluguel", NewRentalScreen(self._services)),
            ("Agenda", RentalsScreen(self._services)),
            ("Estoque", ProductsScreen(self._services)),
            ("Clientes", CustomersScreen(self._services)),
            ("Financeiro", FinanceScreen(self._services)),
            ("Backup", BackupScreen(self._services)),
        ]

        for index, (label, screen) in enumerate(screens):
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setProperty("nav", True)
            button.setMinimumHeight(52)
            button.clicked.connect(lambda _checked, idx=index: self._stack.setCurrentIndex(idx))
            button_group.addButton(button)
            sidebar_layout.addWidget(button)
            self._stack.addWidget(screen)

        sidebar_layout.addStretch()

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self._stack)

        self.setCentralWidget(central)
        self._apply_styles()
        self._build_menu()
        button_group.buttons()[0].setChecked(True)
        self._stack.setCurrentIndex(0)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#sidebar {
                background-color: #f5f6f8;
            }
            QPushButton[nav="true"] {
                font-size: 16px;
                padding: 12px;
                text-align: left;
                border-radius: 8px;
                background-color: white;
            }
            QPushButton[nav="true"]:hover {
                background-color: #e3ecff;
            }
            QPushButton[nav="true"]:checked {
                background-color: #2d6cdf;
                color: white;
            }
            """
        )

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Arquivo")
        exit_action = file_menu.addAction("Sair")
        exit_action.triggered.connect(self.close)

        help_menu = menu_bar.addMenu("Ajuda")
        help_menu.addAction("Sobre")
