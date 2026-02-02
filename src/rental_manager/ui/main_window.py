"""Main window for the RentalManager application."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    """Primary window with placeholder actions."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RentalManager")
        self.resize(900, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)

        title = QtWidgets.QLabel("RentalManager")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(title)

        button_layout = QtWidgets.QGridLayout()
        buttons = [
            "Novo Aluguel",
            "Agenda",
            "Estoque",
            "Clientes",
            "Financeiro",
            "Backup",
        ]

        for index, label in enumerate(buttons):
            button = QtWidgets.QPushButton(label)
            button.setMinimumHeight(48)
            row, column = divmod(index, 2)
            button_layout.addWidget(button, row, column)

        layout.addLayout(button_layout)
        layout.addStretch()

        self.setCentralWidget(central)
        self._build_menu()

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Arquivo")
        exit_action = file_menu.addAction("Sair")
        exit_action.triggered.connect(self.close)

        help_menu = menu_bar.addMenu("Ajuda")
        help_menu.addAction("Sobre")
