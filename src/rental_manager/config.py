"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass

from rental_manager.version import __app_name__, __company__

APP_NAME = __app_name__
APP_DATA_DIRNAME = "RentalManager"
DB_FILENAME = "rental_manager.db"
BACKUP_DIRNAME = "backups"
BACKUP_RETENTION_COUNT = 30
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
    name="Responsável pelo pedido",
    phone="(11) 99999-9999",
    document="CPF 000.000.000-00",
    address="Rua Exemplo, 123 - Centro",
)


@dataclass(frozen=True)
class AppConfig:
    """Static configuration values for RentalManager."""

    app_name: str = APP_NAME
    organization_name: str = __company__
    organization_domain: str = "gestaointeligente.local"
