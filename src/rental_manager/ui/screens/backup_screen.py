"""Screen for backup and restore."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.paths import get_backup_dir, get_config_path, get_db_path
from rental_manager.ui.app_services import AppServices
from rental_manager.utils.backup import (
    BackupSettings,
    export_backup,
    list_backups,
    load_backup_settings,
    restore_backup,
    save_backup_settings,
)


class BackupScreen(QtWidgets.QWidget):
    """Placeholder screen for backup and restore actions."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._backup_dir = get_backup_dir()
        self._db_path = get_db_path()
        self._config_path = get_config_path()
        self._build_ui()
        self._load_settings()
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

    def _format_backup_label(self, backup: Path) -> str:
        timestamp = datetime.fromtimestamp(backup.stat().st_mtime)
        return f"{backup.name} ({timestamp:%d/%m/%Y %H:%M})"

    def _on_selection_changed(self) -> None:
        self.restore_button.setEnabled(bool(self._get_selected_backup()))

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
            f"Backup criado com sucesso: {backup_path.name}",
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

        try:
            restore_backup(
                backup_path,
                self._db_path,
                confirm_overwrite=lambda: True,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                f"Não foi possível restaurar o backup: {exc}",
            )
            return

        QtWidgets.QMessageBox.information(
            self,
            "Sucesso",
            "Backup restaurado. O aplicativo será fechado para concluir a "
            "restauração.",
        )
        try:
            self._services.connection.close()
        except Exception:
            pass
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()

    def _on_open_folder(self) -> None:
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(self._backup_dir))
        )

    def _on_auto_backup_changed(self) -> None:
        self._save_settings()
