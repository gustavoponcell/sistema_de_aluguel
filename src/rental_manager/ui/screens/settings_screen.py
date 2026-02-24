"""Application settings UI for the flow-only assistant."""

from __future__ import annotations

from PySide6 import QtWidgets

from rental_manager.ui.app_services import AppServices
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.utils.assistant_settings import (
    AssistantSettings,
    ensure_assistant_section,
    load_assistant_settings,
    save_assistant_settings,
)


class SettingsScreen(BaseScreen):
    """Simple preferences to enable/disable intelligent flows."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._config_path = services.config_path
        self._settings: AssistantSettings = ensure_assistant_section(self._config_path)
        self._build_ui()
        self._apply_settings()

    def refresh(self) -> None:
        self._settings = load_assistant_settings(self._config_path)
        self._apply_settings()

    # UI construction ---------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("Configurações do Assistente")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        description = QtWidgets.QLabel(
            "Os Fluxos Inteligentes funcionam 100% offline. Use estas opções para "
            "desativar temporariamente o assistente ou exibir uma mensagem de manutenção."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self._flows_checkbox = QtWidgets.QCheckBox("Habilitar Fluxos Inteligentes")
        layout.addWidget(self._flows_checkbox)

        message_label = QtWidgets.QLabel("Mensagem exibida quando os fluxos estiverem desativados")
        layout.addWidget(message_label)

        self._message_edit = QtWidgets.QPlainTextEdit()
        self._message_edit.setPlaceholderText("Ex.: Sistema em manutenção até 14h.")
        self._message_edit.setFixedHeight(120)
        layout.addWidget(self._message_edit)

        button_row = QtWidgets.QHBoxLayout()
        self._save_button = QtWidgets.QPushButton("Salvar preferências")
        self._save_button.clicked.connect(self._on_save_clicked)
        button_row.addWidget(self._save_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setWordWrap(True)
        self._set_status("")
        layout.addWidget(self._status_label)

        layout.addStretch(1)

    # Event handlers ----------------------------------------------------
    def _apply_settings(self) -> None:
        self._flows_checkbox.setChecked(self._settings.flows_enabled)
        self._message_edit.setPlainText(self._settings.disabled_message)

    def _on_save_clicked(self) -> None:
        self._settings.flows_enabled = self._flows_checkbox.isChecked()
        self._settings.disabled_message = self._message_edit.toPlainText().strip()
        try:
            save_assistant_settings(self._config_path, self._settings)
        except OSError:
            self._set_status("Não foi possível salvar o arquivo de configuração.", success=False)
            return
        self._set_status("Preferências salvas com sucesso.", success=True)

    def _set_status(self, message: str, success: bool | None = None) -> None:
        if success is True:
            color = "#1a7f37"
        elif success is False:
            color = "#a5281f"
        else:
            color = "#475569"
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_label.setText(message)
