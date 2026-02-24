"""Shared event bus for UI refresh signals."""

from __future__ import annotations

from PySide6 import QtCore


class DataEventBus(QtCore.QObject):
    """Global signal emitter for data change events."""

    data_changed = QtCore.Signal(str)

    def emit_change(self, category: str = "global") -> None:
        """Emit a categorized data change event."""
        self.data_changed.emit(category)
