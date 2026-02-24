"""Card widgets with theme-aware styling."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from rental_manager.utils.theme import ThemeManager


class KpiCard(QtWidgets.QFrame):
    """Summary card with title and value."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        title: str,
        value: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.setObjectName("KpiCard")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self._title_label = QtWidgets.QLabel(title)
        self._title_label.setObjectName("KpiTitle")
        self._value_label = QtWidgets.QLabel(value)
        self._value_label.setObjectName("KpiValue")

        layout.addWidget(self._title_label)
        layout.addWidget(self._value_label)

        self._theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme()

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def apply_theme(self) -> None:
        if self._theme_manager.is_dark():
            stylesheet = """
            QFrame#KpiCard {
                background: #2b2f36;
                border: 1px solid #3a3f48;
                border-radius: 12px;
            }
            QLabel#KpiTitle {
                color: rgba(255, 255, 255, 0.82);
                font-weight: 600;
                font-size: 13px;
            }
            QLabel#KpiValue {
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }
            """
        else:
            stylesheet = """
            QFrame#KpiCard {
                background: #ffffff;
                border: 1px solid rgba(0, 0, 0, 0.10);
                border-radius: 12px;
            }
            QLabel#KpiTitle {
                color: rgba(0, 0, 0, 0.70);
                font-weight: 600;
                font-size: 13px;
            }
            QLabel#KpiValue {
                color: rgba(0, 0, 0, 0.92);
                font-size: 22px;
                font-weight: 700;
            }
            """
        self.setStyleSheet(stylesheet)


class InfoBanner(QtWidgets.QFrame):
    """Banner with title, subtitle and rich content."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        title: str,
        subtitle: str,
        content: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.setObjectName("InfoBanner")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self._title_label = QtWidgets.QLabel(title)
        self._title_label.setObjectName("InfoTitle")
        self._subtitle_label = QtWidgets.QLabel(subtitle)
        self._subtitle_label.setObjectName("InfoSubtitle")
        self._content_label = QtWidgets.QLabel(content)
        self._content_label.setObjectName("InfoContent")
        self._content_label.setWordWrap(True)
        self._content_label.setTextFormat(QtCore.Qt.RichText)

        layout.addWidget(self._title_label)
        layout.addWidget(self._subtitle_label)
        layout.addWidget(self._content_label)

        self._theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme()

    def set_subtitle(self, text: str) -> None:
        self._subtitle_label.setText(text)

    def set_content(self, text: str) -> None:
        self._content_label.setText(text)

    def apply_theme(self) -> None:
        if self._theme_manager.is_dark():
            stylesheet = """
            QFrame#InfoBanner {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
            }
            QLabel#InfoTitle {
                color: #ffffff;
                font-weight: 700;
                font-size: 18px;
            }
            QLabel#InfoSubtitle {
                color: rgba(255, 255, 255, 0.72);
                font-size: 13px;
            }
            QLabel#InfoContent {
                color: rgba(255, 255, 255, 0.9);
                font-size: 13px;
            }
            """
        else:
            stylesheet = """
            QFrame#InfoBanner {
                background: #fff7d6;
                border: 1px solid rgba(0, 0, 0, 0.10);
                border-radius: 12px;
            }
            QLabel#InfoTitle {
                color: rgba(0, 0, 0, 0.92);
                font-weight: 700;
                font-size: 18px;
            }
            QLabel#InfoSubtitle {
                color: rgba(0, 0, 0, 0.70);
                font-size: 13px;
            }
            QLabel#InfoContent {
                color: rgba(0, 0, 0, 0.88);
                font-size: 13px;
            }
            """
        self.setStyleSheet(stylesheet)
