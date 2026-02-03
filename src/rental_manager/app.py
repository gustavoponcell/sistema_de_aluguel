"""Application entry point."""

from __future__ import annotations

import sys

from PySide6 import QtWidgets

from rental_manager.config import AppConfig
from rental_manager.db.connection import get_connection
from rental_manager.db.migrations import apply_migrations
from rental_manager.logging_config import configure_logging, get_logger
from rental_manager.paths import (
    get_app_data_dir,
    get_backup_dir,
    get_config_path,
    get_db_path,
    get_logs_dir,
)
from rental_manager.repositories import CustomerRepo, ProductRepo
from rental_manager.services.inventory_service import InventoryService
from rental_manager.services.payment_service import PaymentService
from rental_manager.services.rental_service import RentalService
from rental_manager.ui.app_services import AppServices
from rental_manager.ui.data_bus import DataEventBus
from rental_manager.ui.main_window import MainWindow
from rental_manager.utils.backup import export_backup, load_backup_settings
from rental_manager.utils.theme import apply_theme_from_choice, load_theme_settings


def main() -> int:
    """Start the RentalManager application."""
    configure_logging()
    get_app_data_dir()
    get_backup_dir()
    get_logs_dir()
    connection = get_connection(get_db_path())
    apply_migrations(connection)

    config = AppConfig()
    logger = get_logger(__name__)
    logger.info("Starting %s", config.app_name)
    backup_settings = load_backup_settings(get_config_path())
    if backup_settings.auto_backup_on_start:
        try:
            backup_path = export_backup(get_db_path(), get_backup_dir())
            logger.info("Backup automático criado em %s", backup_path)
        except Exception:
            logger.exception("Falha ao criar backup automático.")

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setOrganizationName(config.organization_name)
    app.setOrganizationDomain(config.organization_domain)
    theme_settings = load_theme_settings(get_config_path())
    if not apply_theme_from_choice(app, theme_settings.theme):
        logger.warning("Falha ao aplicar tema. Usando estilo padrão.")

    services = AppServices(
        connection=connection,
        data_bus=DataEventBus(),
        customer_repo=CustomerRepo(connection),
        product_repo=ProductRepo(connection),
        inventory_service=InventoryService(connection),
        rental_service=RentalService(connection),
        payment_service=PaymentService(connection),
    )

    window = MainWindow(services)
    app.aboutToQuit.connect(connection.close)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
