"""Shared event bus for UI refresh signals."""

from __future__ import annotations

from PySide6 import QtCore


class DataEventBus(QtCore.QObject):
    """Global signal emitter for data change events."""

    data_changed = QtCore.Signal()
