"""Main window for the RentalManager application."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens import (
    BackupScreen,
    CustomersScreen,
    FinanceScreen,
    NewRentalScreen,
    ProductsScreen,
    RentalsScreen,
)
from rental_manager.ui.strings import APP_NAME
from rental_manager.utils.theme import ThemeSettings


class MainWindow(QtWidgets.QMainWindow):
    """Primary window with navigation and stacked screens."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._stack = QtWidgets.QStackedWidget()
        self._theme_manager = services.theme_manager
        self.setWindowTitle(APP_NAME)
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

        title = QtWidgets.QLabel(APP_NAME)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        title.setAlignment(QtCore.Qt.AlignLeft)

        sidebar_layout.addWidget(title)

        button_group = QtWidgets.QButtonGroup(self)
        button_group.setExclusive(True)

        self._finance_screen = FinanceScreen(self._services)
        self._rentals_screen = RentalsScreen(self._services)
        screens = [
            ("Novo Pedido", NewRentalScreen(self._services)),
            ("Agenda", self._rentals_screen),
            ("Estoque", ProductsScreen(self._services)),
            ("Clientes", CustomersScreen(self._services)),
            ("Financeiro", self._finance_screen),
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
        self._stack.currentChanged.connect(self._on_screen_changed)

    def _on_screen_changed(self, index: int) -> None:
        screen = self._stack.widget(index)
        refresh = getattr(screen, "refresh", None)
        if callable(refresh):
            refresh()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QPushButton[nav="true"] {
                font-size: 16px;
                padding: 12px;
                text-align: left;
                border-radius: 8px;
            }
            """
        )

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Arquivo")
        exit_action = file_menu.addAction("Sair")
        exit_action.triggered.connect(self.close)

        view_menu = menu_bar.addMenu("Exibir")
        theme_menu = view_menu.addMenu("Tema")
        action_group_cls = getattr(QtGui, "QActionGroup", None)
        theme_group = action_group_cls(self) if action_group_cls is not None else None
        if theme_group is not None:
            theme_group.setExclusive(True)
        theme_actions = {
            "light": theme_menu.addAction("Claro"),
            "dark": theme_menu.addAction("Escuro"),
            "system": theme_menu.addAction("Sistema"),
        }
        for key, action in theme_actions.items():
            action.setCheckable(True)
            action.setData(key)
            if theme_group is not None:
                theme_group.addAction(action)
            else:
                action.triggered.connect(
                    lambda _checked=False, act=action: self._on_theme_selected(act)
                )

        current_theme = self._theme_manager.theme_choice
        if current_theme not in theme_actions:
            current_theme = "system"
        theme_actions[current_theme].setChecked(True)
        if theme_group is not None:
            theme_group.triggered.connect(self._on_theme_selected)

        help_menu = menu_bar.addMenu("Ajuda")
        help_menu.addAction("Sobre")

    def _on_theme_selected(self, action: QtGui.QAction) -> None:
        theme_choice = action.data()
        if theme_choice not in ("light", "dark", "system"):
            theme_choice = "system"
        settings = ThemeSettings(theme=theme_choice)
        self._theme_manager.set_theme(settings.theme)
