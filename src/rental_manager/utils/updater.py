"""Update utilities for GitHub Releases."""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rental_manager.logging_config import get_logger
from rental_manager.utils.config_store import load_config_data, save_config_data

GITHUB_API_BASE = "https://api.github.com/repos"
DEFAULT_UPDATE_PROVIDER = "github"
DEFAULT_UPDATE_OWNER = "gustavoponcell"
DEFAULT_UPDATE_REPO = "sistema_de_aluguel"
DEFAULT_ASSET_PREFIX = "GestaoInteligente-Setup-"


@dataclass(frozen=True)
class UpdateSettings:
    """Persisted updater settings."""

    provider: str
    owner: str
    repo: str
    asset_prefix: str
    enabled: bool = True

    @property
    def repo_slug(self) -> str:
        if not self.owner or not self.repo:
            return ""
        return f"{self.owner}/{self.repo}"


@dataclass(frozen=True)
class UpdateCheckResult:
    """Outcome of an update check."""

    status: str
    current_version: str
    latest_version: str | None = None
    notes: str | None = None
    download_url: str | None = None
    message: str | None = None


def normalize_version(version: str) -> str:
    return version.strip().lstrip("v").strip()


def parse_version(version: str) -> tuple[int, int, int]:
    normalized = normalize_version(version)
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", normalized)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def compare_versions(current: str, latest: str) -> int:
    current_tuple = parse_version(current)
    latest_tuple = parse_version(latest)
    if current_tuple == latest_tuple:
        return 0
    if current_tuple < latest_tuple:
        return -1
    return 1


def _extract_repo_from_remote(remote: str) -> str | None:
    https_match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)", remote)
    if https_match:
        return f"{https_match.group('owner')}/{https_match.group('repo')}"
    return None


def get_repo_from_git_config(start_path: Path | None = None) -> str | None:
    if start_path is None:
        start_path = Path(__file__).resolve()
    for parent in [start_path, *start_path.parents]:
        config_path = parent / ".git" / "config"
        if config_path.exists():
            content = config_path.read_text(encoding="utf-8", errors="ignore")
            remotes = re.findall(r"url\s*=\s*(.+)", content)
            for remote in remotes:
                repo = _extract_repo_from_remote(remote.strip())
                if repo:
                    return repo
            break
    return None


def get_repo_from_config(config_path: Path) -> str | None:
    data = load_config_data(config_path)
    updates = data.get("updates")
    if isinstance(updates, dict):
        repo = updates.get("repo")
        if isinstance(repo, str) and repo.strip():
            return repo.strip()
    return None


def _coerce_update_settings(raw: dict[str, Any]) -> UpdateSettings:
    provider = raw.get("provider")
    if not isinstance(provider, str) or not provider.strip():
        provider = DEFAULT_UPDATE_PROVIDER
    else:
        provider = provider.strip()

    raw_owner = raw.get("owner")
    owner = raw_owner.strip() if isinstance(raw_owner, str) else ""
    raw_repo = raw.get("repo")
    repo = raw_repo.strip() if isinstance(raw_repo, str) else ""
    if not owner and "/" in repo:
        owner, repo = repo.split("/", 1)
        owner = owner.strip()
        repo = repo.strip()
    if not owner:
        owner = DEFAULT_UPDATE_OWNER
    if not repo:
        repo = DEFAULT_UPDATE_REPO

    asset_prefix = raw.get("asset_prefix")
    if not isinstance(asset_prefix, str):
        asset_prefix = DEFAULT_ASSET_PREFIX
    else:
        asset_prefix = asset_prefix.strip()

    enabled = raw.get("enabled")
    if not isinstance(enabled, bool):
        enabled = True

    return UpdateSettings(
        provider=provider,
        owner=owner,
        repo=repo,
        asset_prefix=asset_prefix,
        enabled=enabled,
    )


def ensure_update_settings(config_path: Path) -> UpdateSettings:
    """Ensure updater settings exist on disk and return them."""
    data = load_config_data(config_path)
    updates = data.get("updates")
    if not isinstance(updates, dict):
        updates = {}
    settings = _coerce_update_settings(updates)
    desired_updates = {
        "provider": settings.provider,
        "owner": settings.owner,
        "repo": settings.repo,
        "asset_prefix": settings.asset_prefix,
        "enabled": settings.enabled,
    }
    if updates != desired_updates:
        data["updates"] = desired_updates
        save_config_data(config_path, data)
    return settings


def load_update_settings(config_path: Path) -> UpdateSettings:
    data = load_config_data(config_path)
    updates = data.get("updates")
    if not isinstance(updates, dict):
        updates = {}
    return _coerce_update_settings(updates)


def resolve_repo(config_path: Path) -> str | None:
    settings = load_update_settings(config_path)
    if settings.provider == "github" and settings.repo_slug:
        return settings.repo_slug
    repo = get_repo_from_git_config()
    if repo:
        return repo
    return get_repo_from_config(config_path)


def _select_asset(
    assets: list[dict[str, Any]], asset_prefix: str | None
) -> str | None:
    normalized_prefix = asset_prefix.strip().lower() if asset_prefix else ""
    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        name_lower = name.lower()
        if not name_lower.endswith(".exe"):
            continue
        if normalized_prefix and normalized_prefix in name_lower:
            return url
    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        if name.lower().endswith(".exe"):
            return url
    return None


def _fetch_latest_release(repo: str) -> dict[str, Any]:
    url = f"{GITHUB_API_BASE}/{repo}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GestaoInteligente-Updater",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def check_for_updates(config_path: Path, current_version: str) -> UpdateCheckResult:
    logger = get_logger(__name__)
    settings = load_update_settings(config_path)
    if not settings.enabled:
        return UpdateCheckResult(
            status="disabled",
            current_version=current_version,
            message="Atualizações desativadas nas configurações.",
        )
    repo = resolve_repo(config_path)
    if not repo:
        return UpdateCheckResult(
            status="no_repo",
            current_version=current_version,
            message="Repositório não configurado para atualizações.",
        )
    try:
        release = _fetch_latest_release(repo)
    except urllib.error.HTTPError as exc:
        logger.exception("Falha HTTP ao verificar atualizações.")
        if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
            message = (
                "Limite de requisições do GitHub atingido. Tente novamente mais tarde."
            )
        else:
            message = f"Não foi possível verificar atualizações (HTTP {exc.code})."
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            message=message,
        )
    except (urllib.error.URLError, socket.timeout) as exc:
        logger.exception("Falha de conexão ao verificar atualizações.")
        message = "Sem conexão para verificar atualizações."
        return UpdateCheckResult(
            status="no_connection",
            current_version=current_version,
            message=message,
        )
    except json.JSONDecodeError as exc:
        logger.exception("Resposta inválida do GitHub.")
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            message="Não foi possível verificar atualizações.",
        )

    tag_name = release.get("tag_name", "")
    latest_version = normalize_version(tag_name) if isinstance(tag_name, str) else ""
    if not latest_version:
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            message="Release inválido: tag_name ausente.",
        )

    comparison = compare_versions(current_version, latest_version)
    if comparison >= 0:
        return UpdateCheckResult(
            status="up_to_date",
            current_version=current_version,
            latest_version=latest_version,
            message=f"Você já está na versão {current_version}.",
        )

    assets = release.get("assets", [])
    download_url = None
    if isinstance(assets, list):
        download_url = _select_asset(assets, settings.asset_prefix)

    notes = release.get("body")
    if isinstance(notes, str):
        notes = notes.strip()
    else:
        notes = None

    return UpdateCheckResult(
        status="update_available",
        current_version=current_version,
        latest_version=latest_version,
        notes=notes,
        download_url=download_url,
    )
