"""Screen for creating a new rental."""

from __future__ import annotations

from PySide6 import QtWidgets

from rental_manager.ui.app_services import AppServices


class NewRentalScreen(QtWidgets.QWidget):
    """Placeholder screen for new rental workflow."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Novo Aluguel")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Inicie um novo aluguel com dados do cliente, datas e itens."
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
