"""Screen for customer management."""

from __future__ import annotations

from PySide6 import QtWidgets

from rental_manager.ui.app_services import AppServices


class CustomersScreen(QtWidgets.QWidget):
    """Placeholder screen for customers."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Clientes")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Cadastre clientes e acesse rapidamente o histórico de aluguéis."
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
