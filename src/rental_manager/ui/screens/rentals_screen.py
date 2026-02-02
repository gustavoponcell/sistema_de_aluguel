"""Screen for rentals agenda."""

from __future__ import annotations

from PySide6 import QtWidgets

from rental_manager.ui.app_services import AppServices


class RentalsScreen(QtWidgets.QWidget):
    """Placeholder screen for the rentals agenda."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Agenda")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        subtitle = QtWidgets.QLabel(
            "Consulte os aluguéis agendados, filtre por datas e status."
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
