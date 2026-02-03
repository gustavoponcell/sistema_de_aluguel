"""Backup utilities for exporting and restoring SQLite databases."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from rental_manager.paths import get_backup_dir
from rental_manager.utils.config_store import load_config_data, save_config_data

EXPECTED_TABLES = {"products", "customers", "rentals", "rental_items"}


@dataclass(frozen=True)
class BackupSettings:
    """Persisted backup settings."""

    auto_backup_on_start: bool = False


def load_backup_settings(config_path: Path) -> BackupSettings:
    """Load backup settings from disk."""
    data = load_config_data(config_path)
    return BackupSettings(
        auto_backup_on_start=bool(data.get("auto_backup_on_start", False))
    )


def save_backup_settings(config_path: Path, settings: BackupSettings) -> None:
    """Save backup settings to disk."""
    payload = load_config_data(config_path)
    payload["auto_backup_on_start"] = settings.auto_backup_on_start
    save_config_data(config_path, payload)


def export_backup(db_path: Path | str, backup_dir: Path | str) -> Path:
    """Copy the SQLite database file into a timestamped backup file."""
    database_path = Path(db_path)
    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if not database_path.exists():
        raise FileNotFoundError("Banco de dados não encontrado.")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{database_path.stem}_{timestamp}.db"
    backup_path = target_dir / backup_name
    shutil.copy2(database_path, backup_path)
    return backup_path


def restore_backup(
    backup_file: Path | str,
    db_path: Path | str,
    *,
    confirm_overwrite: Callable[[], bool] | None = None,
) -> Path:
    """Restore a backup file into the main SQLite database."""
    if confirm_overwrite is None:
        raise ValueError("A confirmação de sobrescrita é obrigatória.")
    if not confirm_overwrite():
        raise PermissionError("Restauração cancelada pelo usuário.")

    backup_path = Path(backup_file)
    if not backup_path.exists() or not backup_path.is_file():
        raise FileNotFoundError("Arquivo de backup não encontrado.")
    if backup_path.suffix.lower() != ".db":
        raise ValueError("O arquivo selecionado não é um banco de dados .db.")

    _validate_backup_contents(backup_path, EXPECTED_TABLES)

    database_path = Path(db_path)
    export_backup(database_path, get_backup_dir())
    try:
        source = sqlite3.connect(backup_path)
        destination = sqlite3.connect(database_path)
    except sqlite3.Error as exc:
        raise ValueError("Não foi possível abrir o banco de dados para restaurar.") from exc

    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()
    return database_path


def list_backups(backup_dir: Path | str) -> list[Path]:
    """Return a list of backup files sorted by newest first."""
    target_dir = Path(backup_dir)
    if not target_dir.exists():
        return []
    return sorted(
        (path for path in target_dir.glob("*.db") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _validate_backup_contents(backup_path: Path, expected_tables: Iterable[str]) -> None:
    try:
        connection = sqlite3.connect(backup_path)
    except sqlite3.Error as exc:
        raise ValueError("Não foi possível abrir o arquivo de backup.") from exc

    try:
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()

    missing_tables = set(expected_tables) - tables
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise ValueError(
            "O backup selecionado não contém as tabelas esperadas: "
            f"{missing}."
        )
