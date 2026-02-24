"""Reusable dialog to edit custom document text."""

from __future__ import annotations

from PySide6 import QtWidgets


class DocumentTextDialog(QtWidgets.QDialog):
    """Simple text editor dialog for custom document terms."""

    def __init__(self, parent, title: str, initial_text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 360)
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(
            "Revise e ajuste o texto antes de aplicar ao documento."
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self._editor = QtWidgets.QPlainTextEdit()
        self._editor.setPlainText(initial_text)
        layout.addWidget(self._editor, stretch=1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def text(self) -> str:
        """Return the edited content."""
        return self._editor.toPlainText().strip()
