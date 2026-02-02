"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass

APP_NAME = "RentalManager"
APP_DATA_DIRNAME = APP_NAME
DB_FILENAME = "rental_manager.db"
BACKUP_DIRNAME = "backups"
LOGS_DIRNAME = "logs"
LOG_FILENAME = "app.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


@dataclass(frozen=True)
class AppConfig:
    """Static configuration values for RentalManager."""

    app_name: str = APP_NAME
    organization_name: str = APP_NAME
    organization_domain: str = "rentalmanager.local"
