"""Application entry point."""

from __future__ import annotations

import sys

from PySide6 import QtWidgets

from rental_manager.config import AppConfig
from rental_manager.logging_config import configure_logging, get_logger
from rental_manager.paths import get_app_data_dir, get_backup_dir, get_logs_dir
from rental_manager.ui.main_window import MainWindow


def main() -> int:
    """Start the RentalManager application."""
    configure_logging()
    get_app_data_dir()
    get_backup_dir()
    get_logs_dir()

    config = AppConfig()
    logger = get_logger(__name__)
    logger.info("Starting %s", config.app_name)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setOrganizationName(config.organization_name)
    app.setOrganizationDomain(config.organization_domain)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
