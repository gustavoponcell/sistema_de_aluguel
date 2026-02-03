"""Main window for the RentalManager application."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.paths import get_config_path
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
from rental_manager.utils.updater import UpdateCheckResult, check_for_updates
from rental_manager.version import __version__


class UpdateCheckWorker(QtCore.QThread):
    """Background worker to check for updates."""

    completed = QtCore.Signal(UpdateCheckResult)

    def __init__(self, config_path) -> None:
        super().__init__()
        self._config_path = config_path

    def run(self) -> None:
        result = check_for_updates(self._config_path, __version__)
        self.completed.emit(result)


class MainWindow(QtWidgets.QMainWindow):
    """Primary window with navigation and stacked screens."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._stack = QtWidgets.QStackedWidget()
        self._theme_manager = services.theme_manager
        self._update_worker: UpdateCheckWorker | None = None
        self._update_progress: QtWidgets.QProgressDialog | None = None
        self.setWindowTitle(f"{APP_NAME} — v{__version__}")
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
        check_updates_action = help_menu.addAction("Verificar atualizações")
        check_updates_action.triggered.connect(self._on_check_updates)
        about_action = help_menu.addAction("Sobre")
        about_action.triggered.connect(self._show_about)

    def _on_theme_selected(self, action: QtGui.QAction) -> None:
        theme_choice = action.data()
        if theme_choice not in ("light", "dark", "system"):
            theme_choice = "system"
        settings = ThemeSettings(theme=theme_choice)
        self._theme_manager.set_theme(settings.theme)

    def _show_about(self) -> None:
        message = QtWidgets.QMessageBox(self)
        message.setWindowTitle("Sobre")
        message.setIcon(QtWidgets.QMessageBox.Information)
        message.setText(f"{APP_NAME}\nVersão {__version__}")
        message.setStandardButtons(QtWidgets.QMessageBox.Ok)
        message.exec()

    def _on_check_updates(self) -> None:
        if self._update_worker and self._update_worker.isRunning():
            return
        self._update_progress = QtWidgets.QProgressDialog(
            "Verificando atualizações...", None, 0, 0, self
        )
        self._update_progress.setWindowTitle("Atualizações")
        self._update_progress.setWindowModality(QtCore.Qt.WindowModal)
        self._update_progress.setCancelButton(None)
        self._update_progress.show()

        self._update_worker = UpdateCheckWorker(get_config_path())
        self._update_worker.completed.connect(self._handle_update_result)
        self._update_worker.start()

    def _handle_update_result(self, result: UpdateCheckResult) -> None:
        if self._update_progress:
            self._update_progress.close()
            self._update_progress = None
        self._update_worker = None

        if result.status == "update_available":
            self._show_update_available(result)
            return
        if result.status == "up_to_date":
            QtWidgets.QMessageBox.information(
                self, "Atualizações", result.message or "Você já está atualizado."
            )
            return
        if result.status == "no_connection":
            QtWidgets.QMessageBox.warning(
                self,
                "Atualizações",
                result.message or "Sem conexão para verificar atualizações.",
            )
            return
        if result.status == "disabled":
            QtWidgets.QMessageBox.information(
                self,
                "Atualizações",
                result.message or "Atualizações desativadas.",
            )
            return
        if result.status == "no_repo":
            QtWidgets.QMessageBox.warning(
                self,
                "Atualizações",
                result.message
                or "Repositório não configurado para atualizações.",
            )
            return
        QtWidgets.QMessageBox.warning(
            self,
            "Atualizações",
            result.message or "Não foi possível verificar atualizações.",
        )

    def _show_update_available(self, result: UpdateCheckResult) -> None:
        message_box = QtWidgets.QMessageBox(self)
        message_box.setWindowTitle("Atualização disponível")
        message_box.setIcon(QtWidgets.QMessageBox.Information)
        message_box.setText(
            "<b>Atualização disponível</b><br>"
            f"Versão atual: {result.current_version}<br>"
            f"Versão disponível: {result.latest_version}"
        )
        message_box.setInformativeText("Deseja baixar a atualização?")
        if result.notes:
            message_box.setDetailedText(result.notes[:4000])
        download_button = message_box.addButton(
            "Baixar atualização", QtWidgets.QMessageBox.AcceptRole
        )
        message_box.addButton("Cancelar", QtWidgets.QMessageBox.RejectRole)
        message_box.exec()
        if message_box.clickedButton() == download_button:
            if result.download_url:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(result.download_url))
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Atualizações",
                    "Release encontrada, mas nenhum instalador .exe foi localizado nos assets.",
                )
