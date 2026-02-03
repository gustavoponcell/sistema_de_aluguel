"""Theme utilities for RentalManager."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from PySide6 import QtWidgets

from rental_manager.logging_config import get_logger
from rental_manager.utils.config_store import load_config_data, save_config_data

ThemeChoice = Literal["light", "dark", "system"]


@dataclass(frozen=True)
class ThemeSettings:
    """Persisted theme settings."""

    theme: ThemeChoice = "system"


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


def apply_theme(app: QtWidgets.QApplication, theme_name: str) -> None:
    """Apply qdarktheme plus custom tweaks."""
    import qdarktheme

    qdarktheme.setup_theme(theme_name)
    app.setStyleSheet(_theme_stylesheet(theme_name))


def apply_theme_from_choice(
    app: QtWidgets.QApplication, choice: ThemeChoice
) -> str:
    """Apply theme from the given choice and return the actual theme name."""
    theme_name = resolve_theme_choice(choice)
    apply_theme(app, theme_name)
    logger = get_logger(__name__)
    logger.info("Tema aplicado: %s (configurado: %s)", theme_name, choice)
    return theme_name


def _theme_stylesheet(theme_name: str) -> str:
    if theme_name == "dark":
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
    return """
        QHeaderView::section {
            background-color: #f2f4f8;
            color: #222222;
            padding: 6px 8px;
            border: 1px solid #d7dbe3;
        }
        QFrame#sidebar {
            background-color: #f5f6f8;
        }
        QPushButton[nav="true"] {
            background-color: #ffffff;
            color: #111827;
        }
        QPushButton[nav="true"]:hover {
            background-color: #e3ecff;
        }
        QPushButton[nav="true"]:checked {
            background-color: #2d6cdf;
            color: #ffffff;
        }
        QTableView {
            selection-background-color: #2d6cdf;
            selection-color: #ffffff;
            gridline-color: #d7dbe3;
        }
        QTableCornerButton::section {
            background-color: #f2f4f8;
            border: 1px solid #d7dbe3;
        }
        QMessageBox QLabel {
            color: #1f2937;
        }
        QMessageBox QPushButton {
            padding: 6px 12px;
            border-radius: 6px;
        }
        QLineEdit,
        QTextEdit,
        QSpinBox,
        QDoubleSpinBox,
        QPlainTextEdit {
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px;
        }
        QLineEdit:focus,
        QTextEdit:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QPlainTextEdit:focus {
            border: 1px solid #2d6cdf;
        }
    """
