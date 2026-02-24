"""Assistant screen dedicated to intelligent flows."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from rental_manager.ui.app_services import AppServices
from rental_manager.ui.assistant.flows import FlowCategory, FlowDefinition, get_default_categories
from rental_manager.ui.screens.base_screen import BaseScreen
from rental_manager.utils.assistant_audit import log_assistant_event
from rental_manager.utils.assistant_settings import AssistantSettings, load_assistant_settings


def _status_display(code: str) -> tuple[str, str]:
    if code == "disabled":
        return "Assistente desligado", "#f97316"
    if code == "maintenance":
        return "Em manutenção", "#ca8a04"
    return "Operacional", "#15803d"


def _status_stylesheet(color: str) -> str:
    return (
        f"padding: 6px 12px; border-radius: 999px; font-weight: 600; color: #fff; "
        f"background-color: {color};"
    )


class _FlowTile(QtWidgets.QFrame):
    """Card used to trigger a flow dialog."""

    triggered = QtCore.Signal(object)

    def __init__(self, definition: FlowDefinition) -> None:
        super().__init__()
        self._definition = definition
        self.setObjectName("flowTile")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        # Cards previously inherited an Expanding policy and became extremely tall in fullscreen.
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setSizePolicy(size_policy)
        self.setMinimumHeight(88)
        self.setMaximumHeight(132)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        self._title = QtWidgets.QLabel(definition.title)
        self._title.setWordWrap(True)
        self._title.setObjectName("tileTitle")
        layout.addWidget(self._title)
        self._description = QtWidgets.QLabel(definition.description)
        self._description.setWordWrap(True)
        self._description.setObjectName("tileDesc")
        layout.addWidget(self._description)
        layout.addStretch()
        self._button = QtWidgets.QPushButton("Abrir fluxo")
        self._button.clicked.connect(lambda: self.triggered.emit(definition))
        layout.addWidget(self._button, alignment=QtCore.Qt.AlignRight)

    def set_theme(
        self,
        *,
        background: str,
        border: str,
        title_color: str,
        desc_color: str,
        button_qss: str,
    ) -> None:
        self.setStyleSheet(
            f"#flowTile {{ background-color: {background}; border: 1px solid {border}; border-radius: 10px; }}"
            f"#tileTitle {{ color: {title_color}; font-size: 15px; font-weight: 600; }}"
            f"#tileDesc {{ color: {desc_color}; font-size: 12px; }}"
        )
        self._button.setStyleSheet(button_qss)

    def set_enabled(self, enabled: bool) -> None:
        self.setProperty("enabled", enabled)
        self._button.setEnabled(enabled)
        self.setGraphicsEffect(None)


class AssistantScreen(BaseScreen):
    """Assistant dashboard with categorized flows."""

    def __init__(self, services: AppServices) -> None:
        super().__init__(services)
        self._config_path = services.config_path
        self._settings: AssistantSettings = load_assistant_settings(self._config_path)
        self._categories: list[FlowCategory] = get_default_categories()
        self._tiles: list[_FlowTile] = []
        self._flows_enabled = self._settings.flows_enabled
        self._grid_sections: list[tuple[QtWidgets.QGridLayout, list[_FlowTile]]] = []
        self._current_grid_columns = 2

        self._build_ui()
        self._apply_state()
        self._apply_theme_styles()
        self._services.theme_manager.theme_changed.connect(self._on_theme_changed)

    # UI ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setObjectName("assistantRoot")
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Fullscreen fix: wrapping content in a scroll area prevents the old
        # top-level stretch that left giant gaps when maximized.
        self._scroll_area = QtWidgets.QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        root_layout.addWidget(self._scroll_area)

        content = QtWidgets.QWidget()
        self._scroll_area.setWidget(content)
        self._content_layout = QtWidgets.QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 24, 24, 32)
        self._content_layout.setSpacing(14)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)
        title = QtWidgets.QLabel("Assistente inteligente")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        self._status_chip = QtWidgets.QLabel("")
        header.addWidget(self._status_chip, alignment=QtCore.Qt.AlignRight)
        self._content_layout.addLayout(header)

        self._hero_card = QtWidgets.QFrame()
        self._hero_card.setObjectName("heroCard")
        hero_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        hero_policy.setHeightForWidth(False)
        self._hero_card.setSizePolicy(hero_policy)
        self._hero_card.setMinimumHeight(120)
        # Banner height used to explode in fullscreen; cap it to keep proportions.
        self._hero_card.setMaximumHeight(164)
        hero_layout = QtWidgets.QVBoxLayout(self._hero_card)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(8)
        self._hero_status = QtWidgets.QLabel("")
        self._hero_status.setStyleSheet("font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;")
        hero_layout.addWidget(self._hero_status)
        self._hero_title = QtWidgets.QLabel("Central de fluxos")
        self._hero_title.setWordWrap(True)
        self._hero_title.setStyleSheet("font-size: 20px; font-weight: 600;")
        hero_layout.addWidget(self._hero_title)
        self._hero_desc = QtWidgets.QLabel(
            "Execute fluxos operacionais, financeiros e de clientes com validações e filtros dedicados."
        )
        self._hero_desc.setWordWrap(True)
        hero_layout.addWidget(self._hero_desc)
        self._hero_button = QtWidgets.QPushButton("Abrir fluxos")
        self._hero_button.clicked.connect(self._on_hero_clicked)
        self._hero_action = "flows"
        hero_layout.addWidget(self._hero_button, alignment=QtCore.Qt.AlignRight)
        self._content_layout.addWidget(self._hero_card)

        for category in self._categories:
            self._content_layout.addWidget(self._build_category_section(category))
        self._content_layout.addStretch()
        QtCore.QTimer.singleShot(0, self._update_grid_columns)

    def _build_category_section(self, category: FlowCategory) -> QtWidgets.QWidget:
        frame = QtWidgets.QFrame()
        frame.setObjectName("categoryFrame")
        frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(10)
        title = QtWidgets.QLabel(category.name)
        title.setStyleSheet("font-weight: 600; font-size: 16px;")
        frame_layout.addWidget(title)
        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        tiles_for_section: list[_FlowTile] = []
        columns = 2
        for idx, definition in enumerate(category.flows):
            tile = _FlowTile(definition)
            tile.triggered.connect(self._open_flow)
            self._tiles.append(tile)
            tiles_for_section.append(tile)
            row = idx // columns
            col = idx % columns
            grid.addWidget(tile, row, col)
        frame_layout.addLayout(grid)
        for col in range(columns):
            grid.setColumnStretch(col, 1)
        self._grid_sections.append((grid, tiles_for_section))
        return frame

    # State ----------------------------------------------------------------
    def refresh(self) -> None:
        self._apply_state()

    def _apply_state(self) -> None:
        self._settings = load_assistant_settings(self._config_path)
        status_code = self._determine_status()
        status_text, color = _status_display(status_code)
        self._status_chip.setText(status_text)
        self._status_chip.setStyleSheet(_status_stylesheet(color))
        ready = status_code == "ready"
        if status_code == "ready":
            self._hero_title.setText("Fluxos inteligentes prontos")
            self._hero_desc.setText("Escolha uma categoria abaixo para iniciar o fluxo desejado.")
            self._hero_button.setText("Explorar fluxos")
            self._hero_button.setEnabled(True)
            self._hero_action = "flows"
        else:
            self._hero_title.setText("Fluxos desativados")
            hero_desc = self._settings.disabled_message.strip()
            if not hero_desc:
                hero_desc = "Ative os fluxos na tela de Configurações para liberar as automações."
            self._hero_desc.setText(hero_desc)
            self._hero_button.setText("Abrir Configurações")
            self._hero_button.setEnabled(True)
            self._hero_action = "settings"
        self._hero_status.setText(status_text.upper())
        self._set_tiles_enabled(ready)
        self._flows_enabled = ready

    def _determine_status(self) -> str:
        if not self._settings.flows_enabled:
            return "disabled"
        return "ready"

    def _set_tiles_enabled(self, enabled: bool) -> None:
        for tile in self._tiles:
            tile.setEnabled(enabled)
            tile.set_enabled(enabled)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[name-defined]
        super().resizeEvent(event)
        self._update_grid_columns()

    def _update_grid_columns(self) -> None:
        if not hasattr(self, "_scroll_area"):
            return
        viewport_width = self._scroll_area.viewport().width()
        columns = 1 if viewport_width < 760 else 2
        if columns == self._current_grid_columns:
            return
        self._current_grid_columns = columns
        for grid, tiles in self._grid_sections:
            self._reflow_tiles(grid, tiles, columns)

    def _reflow_tiles(
        self,
        grid: QtWidgets.QGridLayout,
        tiles: list[_FlowTile],
        columns: int,
    ) -> None:
        for tile in tiles:
            grid.removeWidget(tile)
        for idx, tile in enumerate(tiles):
            row = idx // columns
            col = idx % columns
            grid.addWidget(tile, row, col)
        for col in range(columns):
            grid.setColumnStretch(col, 1)
        col = columns
        while col < 3:
            grid.setColumnStretch(col, 0)
            col += 1

    # Theme ---------------------------------------------------------------
    def _apply_theme_styles(self) -> None:
        is_dark = self._services.theme_manager.is_dark()
        if is_dark:
            base_bg = "#0f172a"
            hero_bg = "#111e37"
            hero_border = "#1e3a8a"
            tile_bg = "#1b2944"
            border = "#24324f"
            title_color = "#f1f5f9"
            desc_color = "#94a3b8"
            button_qss = "QPushButton { background-color: #2563eb; color: #fff; border-radius: 6px; padding: 8px 16px; } QPushButton:disabled { opacity: 0.5; }"
        else:
            base_bg = "#f7f9fc"
            hero_bg = "#ffffff"
            hero_border = "#cbd5e1"
            tile_bg = "#ffffff"
            border = "#d1d8e5"
            title_color = "#0f172a"
            desc_color = "#475569"
            button_qss = (
                "QPushButton { background-color: #1d4ed8; color: #fff; border-radius: 6px; padding: 8px 16px; }"
                "QPushButton:disabled { opacity: 0.5; }"
            )
        self.setStyleSheet(f"#assistantRoot {{ background-color: {base_bg}; }}")
        self._hero_card.setStyleSheet(
            f"#heroCard {{ background-color: {hero_bg}; border: 1px solid {hero_border}; border-radius: 14px; padding: 18px; }}"
        )
        self._hero_button.setStyleSheet(button_qss)
        for tile in self._tiles:
            tile.set_theme(
                background=tile_bg,
                border=border,
                title_color=title_color,
                desc_color=desc_color,
                button_qss=button_qss,
            )

    def _on_theme_changed(self, theme_name: str) -> None:
        _ = theme_name
        self._apply_theme_styles()

    # Actions -------------------------------------------------------------
    def _on_hero_clicked(self) -> None:
        if getattr(self, "_hero_action", "flows") == "settings":
            self._open_settings()
        else:
            self._focus_first_flow()

    def _focus_first_flow(self) -> None:
        if self._tiles:
            self._tiles[0].setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)

    def _open_flow(self, definition: FlowDefinition) -> None:
        if not self._flows_enabled:
            QtWidgets.QMessageBox.information(
                self,
                "Assistente",
                self._settings.disabled_message.strip()
                or "Os fluxos estão desativados. Ajuste as configurações primeiro.",
            )
            return
        log_assistant_event(f"flow:{definition.code}")
        dialog = definition.dialog_factory(self._services, self)
        dialog.exec()

    def _open_settings(self) -> None:
        window = self.window()
        if window and hasattr(window, "open_settings_screen"):
            window.open_settings_screen()
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Configurações",
                "Abra a tela de Configurações para ativar o assistente.",
            )
