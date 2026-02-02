"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Static configuration values for RentalManager."""

    app_name: str = "RentalManager"
    organization_name: str = "RentalManager"
    organization_domain: str = "rentalmanager.local"
