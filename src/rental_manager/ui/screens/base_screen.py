"""Base class for screens that can refresh their data."""

from __future__ import annotations

from PySide6 import QtWidgets

from rental_manager.ui.app_services import AppServices


class BaseScreen(QtWidgets.QWidget):
    """Base screen with refresh hooks and data change handling."""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._services = services
        self._needs_refresh = False
        self._services.data_bus.data_changed.connect(self._on_data_changed)

    def refresh(self) -> None:
        """Reload data for this screen."""

<<<<<<< HEAD
    def _on_data_changed(self, category: str) -> None:
        if not self._should_refresh(category):
            return
=======
    def _on_data_changed(self) -> None:
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
        if self.isVisible():
            self.refresh()
        else:
            self._needs_refresh = True

<<<<<<< HEAD
    def _should_refresh(self, category: str) -> bool:
        return True

=======
>>>>>>> fedafe265492a1d0f264429ebdab496eddc6884d
    def showEvent(self, event: QtWidgets.QShowEvent) -> None:  # type: ignore[name-defined]
        super().showEvent(event)
        if self._needs_refresh:
            self._needs_refresh = False
            self.refresh()
