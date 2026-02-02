"""Application entry point."""

from __future__ import annotations

import sys

from PySide6 import QtWidgets

from rental_manager.config import AppConfig
from rental_manager.db import init_db
from rental_manager.db.connection import get_connection
from rental_manager.logging_config import configure_logging, get_logger
from rental_manager.paths import (
    get_app_data_dir,
    get_backup_dir,
    get_db_path,
    get_logs_dir,
)
from rental_manager.repositories import CustomerRepo, ProductRepo
from rental_manager.services.inventory_service import InventoryService
from rental_manager.services.rental_service import RentalService
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.main_window import MainWindow


def main() -> int:
    """Start the RentalManager application."""
    configure_logging()
    get_app_data_dir()
    get_backup_dir()
    get_logs_dir()
    init_db(get_db_path())

    config = AppConfig()
    logger = get_logger(__name__)
    logger.info("Starting %s", config.app_name)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setOrganizationName(config.organization_name)
    app.setOrganizationDomain(config.organization_domain)

    connection = get_connection(get_db_path())
    services = AppServices(
        connection=connection,
        customer_repo=CustomerRepo(connection),
        product_repo=ProductRepo(connection),
        inventory_service=InventoryService(connection),
        rental_service=RentalService(connection),
    )

    window = MainWindow(services)
    app.aboutToQuit.connect(connection.close)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
