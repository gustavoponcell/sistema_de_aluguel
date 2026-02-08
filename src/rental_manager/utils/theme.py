"""Theme utilities for RentalManager."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.logging_config import get_logger
from rental_manager.utils.config_store import load_config_data, save_config_data

ThemeChoice = Literal["light", "dark", "system"]

@dataclass(frozen=True)
class ThemeSettings:
    """Persisted theme settings."""

    theme: ThemeChoice = "system"


class ThemeManager(QtCore.QObject):
    """Central theme manager with change notifications."""

    theme_changed = QtCore.Signal(str)

    def __init__(self, app: QtWidgets.QApplication, config_path) -> None:
        super().__init__()
        self._app = app
        self._config_path = config_path
        self._settings = load_theme_settings(config_path)
        self._resolved_theme = resolve_theme_choice(self._settings.theme)
        self._apply_theme()

    @property
    def theme_choice(self) -> ThemeChoice:
        return self._settings.theme

    def set_theme(self, choice: ThemeChoice) -> None:
        if choice not in ("light", "dark", "system"):
            choice = "system"
        self._settings = ThemeSettings(theme=choice)
        logger = get_logger(__name__)
        try:
            save_theme_settings(self._config_path, self._settings)
        except OSError:
            logger.warning("Não foi possível salvar a preferência de tema.")
        self._apply_theme()
        self.theme_changed.emit(self._resolved_theme)

    def is_dark(self) -> bool:
        return self._resolved_theme == "dark"

    def _apply_theme(self) -> None:
        logger = get_logger(__name__)
        if not apply_theme_from_choice(self._app, self._settings.theme):
            logger.warning("Falha ao aplicar tema. Usando estilo padrão.")
        self._resolved_theme = resolve_theme_choice(self._settings.theme)


def load_theme_settings(config_path) -> ThemeSettings:
    """Load theme settings from disk."""
    data = load_config_data(config_path)
    theme = data.get("theme", "system")
    if theme not in ("light", "dark", "system"):
        theme = "system"
    return ThemeSettings(theme=theme)


def save_theme_settings(config_path, settings: ThemeSettings) -> None:
    """Save theme settings to disk."""
    payload = load_config_data(config_path)
    payload["theme"] = settings.theme
    save_config_data(config_path, payload)


def _detect_windows_dark_mode() -> bool | None:
    """Return True if Windows is in dark mode, False if light, None if unknown."""
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore
    except Exception:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return None
    try:
        return bool(int(value) == 0)
    except (TypeError, ValueError):
        return None


def resolve_theme_choice(choice: ThemeChoice) -> str:
    """Resolve a theme choice to an actual theme name."""
    if choice == "light":
        return "light"
    if choice == "dark":
        return "dark"
    detected = _detect_windows_dark_mode()
    if detected is None:
        return "light"
    return "dark" if detected else "light"


def apply_theme(app: QtWidgets.QApplication, theme_name: str) -> bool:
    try:
        app.setStyle("Fusion")
        if theme_name == "dark":
            app.setPalette(_build_dark_palette())
            app.setStyleSheet(_dark_stylesheet())
        else:
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet("")
        return True
    except Exception:
        return False


def apply_theme_from_choice(
    app: QtWidgets.QApplication, choice: ThemeChoice
) -> bool:
    """Apply theme from the given choice and return True if applied."""
    logger = get_logger(__name__)
    try:
        theme_name = resolve_theme_choice(choice)
    except Exception:
        theme_name = "light"
    applied = False
    try:
        applied = apply_theme(app, theme_name)
    except Exception:
        applied = False
    if applied:
        logger.info("Tema aplicado: %s (configurado: %s)", theme_name, choice)
    return applied


def apply_table_theme(table: QtWidgets.QTableView, theme_name: str) -> None:
    """Apply a table-specific theme without touching the global palette."""
    table.setAlternatingRowColors(True)
    if theme_name == "dark":
        palette = table.palette()
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#1f1f1f"))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#242424"))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#f0f0f0"))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#3a3a3a"))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
        table.setPalette(palette)
        table.setStyleSheet(_dark_table_stylesheet())
    else:
        table.setPalette(QtWidgets.QApplication.style().standardPalette())
        table.setStyleSheet("")


def _build_dark_palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(32, 34, 40))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(24, 26, 31))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(32, 34, 40))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(0, 0, 0))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 48, 58))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(45, 108, 223))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor(143, 152, 170))
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(89, 160, 255))
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtGui.QColor(143, 152, 170))
    palette.setColor(
        QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, QtGui.QColor(143, 152, 170)
    )
    palette.setColor(
        QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, QtGui.QColor(143, 152, 170)
    )
    return palette


def _dark_stylesheet() -> str:
    return """
    QHeaderView::section {
        background-color: #2b2f36;
        color: #f1f1f1;
        padding: 6px 8px;
        border: 1px solid #3a3f48;
    }
    QFrame#sidebar {
        background-color: #1f232b;
    }
    QPushButton[nav="true"] {
        background-color: #2b2f36;
        color: #f1f1f1;
    }
    QPushButton[nav="true"]:hover {
        background-color: #343a46;
    }
    QPushButton[nav="true"]:checked {
        background-color: #2d6cdf;
        color: #ffffff;
    }
    QTableView {
        selection-background-color: #2d6cdf;
        selection-color: #ffffff;
        gridline-color: #3a3f48;
    }
    QTableCornerButton::section {
        background-color: #2b2f36;
        border: 1px solid #3a3f48;
    }
    QMessageBox QLabel {
        color: #f1f1f1;
    }
    QMessageBox QPushButton {
        background-color: #3b4252;
        color: #f1f1f1;
        border: 1px solid #4c566a;
        padding: 6px 12px;
        border-radius: 6px;
    }
    QMessageBox QPushButton:hover {
        background-color: #4c566a;
    }
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QPlainTextEdit {
        border: 1px solid #4c566a;
        border-radius: 6px;
        padding: 6px;
    }
    QLineEdit:focus,
    QTextEdit:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus,
    QPlainTextEdit:focus {
        border: 1px solid #7aa2f7;
    }
    QLineEdit:disabled,
    QTextEdit:disabled,
    QSpinBox:disabled,
    QDoubleSpinBox:disabled,
    QPlainTextEdit:disabled {
        color: #8f98aa;
    }
    """


def _dark_table_stylesheet() -> str:
    return """
    QTableWidget, QTableView {
        background-color: #1f1f1f;
        alternate-background-color: #242424;
        color: #f0f0f0;
        gridline-color: #444444;
        selection-background-color: #3a3a3a;
        selection-color: #ffffff;
    }
    QTableWidget::item:selected, QTableView::item:selected {
        background-color: #3a3a3a;
        color: #ffffff;
    }
    QHeaderView::section {
        background-color: #333333;
        color: #f0f0f0;
        border: 1px solid #444444;
        padding: 6px 8px;
    }
    QTableCornerButton::section {
        background-color: #333333;
        border: 1px solid #444444;
    }
    """
