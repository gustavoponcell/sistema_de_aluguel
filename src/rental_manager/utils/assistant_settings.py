"""Assistant settings helpers for flow-only mode."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from rental_manager.utils.config_store import load_config_data, save_config_data


@dataclass(slots=True)
class AssistantSettings:
    """Persisted configuration for the intelligent flows hub."""

    flows_enabled: bool = True
    disabled_message: str = ""


def load_assistant_settings(config_path: Path) -> AssistantSettings:
    """Load assistant settings from disk."""
    data = load_config_data(config_path)
    assistant_data = data.get("assistant", {}) if isinstance(data, dict) else {}
    return AssistantSettings(
        flows_enabled=bool(assistant_data.get("flows_enabled", True)),
        disabled_message=str(assistant_data.get("disabled_message", "") or ""),
    )


def save_assistant_settings(config_path: Path, settings: AssistantSettings) -> None:
    """Persist assistant settings to the JSON config file."""
    payload = load_config_data(config_path)
    payload["assistant"] = asdict(settings)
    save_config_data(config_path, payload)


def ensure_assistant_section(config_path: Path) -> AssistantSettings:
    """Ensure the assistant node exists in the config and return the current values."""
    data = load_config_data(config_path)
    if "assistant" not in data:
        settings = AssistantSettings()
        data["assistant"] = asdict(settings)
        save_config_data(config_path, data)
        return settings
    return load_assistant_settings(config_path)
