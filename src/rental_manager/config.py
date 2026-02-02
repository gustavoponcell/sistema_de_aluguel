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
PDF_DIRNAME = "pdfs"
EXPORTS_DIRNAME = "exports"
CONFIG_FILENAME = "config.json"


@dataclass(frozen=True)
class PdfIssuerInfo:
    """Issuer information for rental PDFs."""

    name: str
    phone: str
    document: str
    address: str


PDF_ISSUER = PdfIssuerInfo(
    name="Responsável pelo aluguel",
    phone="(11) 99999-9999",
    document="CPF 000.000.000-00",
    address="Rua Exemplo, 123 - Centro",
)


@dataclass(frozen=True)
class AppConfig:
    """Static configuration values for RentalManager."""

    app_name: str = APP_NAME
    organization_name: str = APP_NAME
    organization_domain: str = "rentalmanager.local"
