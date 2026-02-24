"""Screen for backup and restore."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.db.connection import get_connection
from rental_manager.logging_config import get_logger
from rental_manager.paths import get_backup_dir, get_config_path, get_db_path
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.utils.backup import (
    BackupSettings,
    export_backup,
    list_backups,
    load_backup_settings,
    prepare_for_restore,
    restore_backup,
    save_backup_settings,
)


class BackupScreen(BaseScreen):
    """Screen for backup and restore actions."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._logger = get_logger("BackupScreen")
        self._connection_detached = False
        self._busy = False
        self._shutting_down = False
        self._backup_dir = get_backup_dir()
        self._db_path = get_db_path()
        self._config_path = get_config_path()
        self._build_ui()
        self._load_settings()
        self._refresh_backups()

    def refresh(self) -> None:
        self._refresh_backups()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Backup")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Gere uma cópia de segurança do banco de dados ou restaure um backup."
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        controls_layout = QtWidgets.QHBoxLayout()
        self.backup_now_button = QtWidgets.QPushButton("Fazer Backup Agora")
        self.restore_button = QtWidgets.QPushButton("Restaurar Backup Selecionado")
        self.open_folder_button = QtWidgets.QPushButton("Abrir pasta de backups")
        self.restore_button.setEnabled(False)
        self.backup_now_button.clicked.connect(self._on_backup_now)
        self.restore_button.clicked.connect(self._on_restore_selected)
        self.open_folder_button.clicked.connect(self._on_open_folder)

        controls_layout.addWidget(self.backup_now_button)
        controls_layout.addWidget(self.restore_button)
        controls_layout.addWidget(self.open_folder_button)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        self.backup_list = QtWidgets.QListWidget()
        self.backup_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.backup_list.itemSelectionChanged.connect(
            self._on_selection_changed
        )
        layout.addWidget(self.backup_list)

        self.status_label = QtWidgets.QLabel()
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

        self.auto_backup_checkbox = QtWidgets.QCheckBox(
            "Backup automático ao iniciar"
        )
        self.auto_backup_checkbox.stateChanged.connect(
            self._on_auto_backup_changed
        )
        layout.addWidget(self.auto_backup_checkbox)

        layout.addStretch()


    def _set_busy_state(self, busy: bool, message: str | None = None) -> None:
        if message:
            self.status_label.setText(message)
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()
        controls_enabled = (not busy) and (not self._shutting_down)
        self.backup_now_button.setEnabled(controls_enabled)
        self.open_folder_button.setEnabled(controls_enabled)
        self.auto_backup_checkbox.setEnabled(controls_enabled)
        self._update_restore_button_state()

    def _wait_for_background_tasks(self) -> None:
        pool = QtCore.QThreadPool.globalInstance()
        try:
            pool.waitForDone(2000)
        except Exception:
            self._logger.debug("Falha ao aguardar threads antes do restore.", exc_info=True)

    def _prepare_for_restore(self) -> None:
        self._logger.info("Finalizando atividades antes da restauração.")
        self._wait_for_background_tasks()
        prepare_for_restore(self._services.connection)
        self._connection_detached = True

    def _restore_connections(self) -> None:
        if not self._connection_detached:
            return
        self._logger.info("Reabrindo conexão principal após falha na restauração.")
        try:
            new_connection = get_connection(self._db_path)
        except Exception as exc:
            self._logger.exception("Falha ao reabrir conexão.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                f"Não foi possível reabrir o banco de dados após a falha: {exc}",
            )
            return
        services = self._services
        object.__setattr__(services, "connection", new_connection)
        for repo in (
            services.customer_repo,
            services.document_repo,
            services.product_repo,
        ):
            repo._connection = new_connection
        services.inventory_service._connection = new_connection
        services.order_service._connection = new_connection
        services.rental_service._connection = new_connection
        services.payment_service._connection = new_connection
        services.expense_service._connection = new_connection
        services.order_service._inventory_service = services.inventory_service
        services.rental_service._order_service = services.order_service
        services.payment_service._repo._connection = new_connection
        services.rental_service._payment_repo._connection = new_connection
        services.expense_service._repo._connection = new_connection
        self._connection_detached = False

    def _handle_restore_error(self, exc: Exception) -> None:
        if isinstance(exc, FileNotFoundError):
            message = "O arquivo selecionado não existe mais."
        elif isinstance(exc, PermissionError):
            message = "Permissão negada ao acessar os arquivos de backup."
        elif isinstance(exc, RuntimeError):
            lower = str(exc).lower()
            if "integrity_check" in lower:
                message = "A verificação de integridade falhou. O backup pode estar corrompido."
            elif "locked" in lower:
                message = "O banco estava em uso. Feche o aplicativo e tente novamente."
            else:
                message = str(exc)
        else:
            message = str(exc)
        QtWidgets.QMessageBox.critical(
            self,
            "Erro na restauração",
            message,
        )

    def _show_restore_success(self, result, backup_path: Path) -> None:
        message = (
            "Backup restaurado com sucesso.\n"
            f"Arquivo restaurado: {backup_path}\n"
            f"Backup de segurança: {result.safety_backup_path}\n"
            "Verificação de integridade: "
            f"{'; '.join(result.integrity_check_results)}\n\n"
            "O aplicativo será fechado para concluir a restauração."
        )
        QtWidgets.QMessageBox.information(
            self,
            "Sucesso",
            message,
        )

    def _load_settings(self) -> None:
        settings = load_backup_settings(self._config_path)
        self.auto_backup_checkbox.setChecked(settings.auto_backup_on_start)

    def _save_settings(self) -> None:
        settings = BackupSettings(
            auto_backup_on_start=self.auto_backup_checkbox.isChecked()
        )
        try:
            save_backup_settings(self._config_path, settings)
        except OSError:
            QtWidgets.QMessageBox.warning(
                self,
                "Atenção",
                "Não foi possível salvar as configurações de backup.",
            )

    def _refresh_backups(self) -> None:
        self.backup_list.clear()
        backups = list_backups(self._backup_dir)
        if not backups:
            self.status_label.setText("Nenhum backup encontrado.")
            self.restore_button.setEnabled(False)
            return

        self.status_label.setText(f"{len(backups)} backup(s) encontrado(s).")
        for backup in backups:
            item = QtWidgets.QListWidgetItem(self._format_backup_label(backup))
            item.setData(QtCore.Qt.UserRole, backup)
            self.backup_list.addItem(item)
        self._update_restore_button_state()

    def _update_restore_button_state(self) -> None:
        if self._busy or self._shutting_down:
            self.restore_button.setEnabled(False)
            return
        self.restore_button.setEnabled(bool(self._get_selected_backup()))

    def _format_backup_label(self, backup: Path) -> str:
        timestamp = datetime.fromtimestamp(backup.stat().st_mtime)
        return f"{backup.name} ({timestamp:%d/%m/%Y %H:%M})"

    def _on_selection_changed(self) -> None:
        self._update_restore_button_state()

    def _get_selected_backup(self) -> Path | None:
        items = self.backup_list.selectedItems()
        if not items:
            return None
        return items[0].data(QtCore.Qt.UserRole)

    def _on_backup_now(self) -> None:
        try:
            backup_path = export_backup(self._db_path, self._backup_dir)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                f"Não foi possível criar o backup: {exc}",
            )
            return

        self._refresh_backups()
        QtWidgets.QMessageBox.information(
            self,
            "Sucesso",
            "Backup criado com sucesso.\n"
            f"Arquivo: {backup_path}",
        )

    def _on_restore_selected(self) -> None:
        backup_path = self._get_selected_backup()
        if not backup_path:
            QtWidgets.QMessageBox.warning(
                self,
                "Atenção",
                "Selecione um backup para restaurar.",
            )
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirmação",
            "Esta ação vai sobrescrever o banco de dados atual. "
            "Deseja continuar?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        text, accepted = QtWidgets.QInputDialog.getText(
            self,
            "Confirmação",
            "Digite RESTAURAR para confirmar:",
        )
        if not accepted or text.strip().upper() != "RESTAURAR":
            QtWidgets.QMessageBox.warning(
                self,
                "Atenção",
                "A restauração foi cancelada.",
            )
            return

        self._set_busy_state(True, "Preparando restauração...")
        QtWidgets.QApplication.processEvents()
        try:
            self._prepare_for_restore()
            result = restore_backup(
                backup_path,
                self._db_path,
                confirm_overwrite=lambda: True,
            )
        except Exception as exc:
            self._logger.exception("Falha ao restaurar backup.")
            self._handle_restore_error(exc)
            self._restore_connections()
            self._set_busy_state(False)
            return

        self._shutting_down = True
        self._set_busy_state(False)
        self._show_restore_success(result, backup_path)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()

    def _on_open_folder(self) -> None:
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(self._backup_dir))
        )

    def _on_auto_backup_changed(self) -> None:
        self._save_settings()
