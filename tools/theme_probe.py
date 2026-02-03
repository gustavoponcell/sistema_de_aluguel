"""Probe qdarktheme APIs and apply themes safely."""

from __future__ import annotations

import sys

from PySide6 import QtWidgets

import qdarktheme

from rental_manager.utils.theme import apply_theme


def main() -> int:
    version = getattr(qdarktheme, "__version__", "unknown")
    print(f"qdarktheme version: {version}")
    print("qdarktheme dir:")
    print(dir(qdarktheme))
    app = QtWidgets.QApplication(sys.argv)
    for theme_name in ("dark", "light"):
        result = apply_theme(app, theme_name)
        print(f"apply_theme({theme_name}) -> {result}")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
