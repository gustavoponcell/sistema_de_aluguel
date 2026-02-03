"""Update utilities for GitHub Releases."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rental_manager.utils.config_store import load_config_data

GITHUB_API_BASE = "https://api.github.com/repos"


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


def resolve_repo(config_path: Path) -> str | None:
    repo = get_repo_from_git_config()
    if repo:
        return repo
    return get_repo_from_config(config_path)


def _select_asset(assets: list[dict[str, Any]], version: str) -> str | None:
    normalized_version = normalize_version(version)
    patterns = [
        re.compile(r".*GestaoInteligente-Setup", re.IGNORECASE),
        re.compile(rf".*-Setup-{re.escape(normalized_version)}\.exe$", re.IGNORECASE),
        re.compile(r".*Setup\.exe$", re.IGNORECASE),
    ]
    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        for pattern in patterns:
            if pattern.match(name):
                return url
    return None


def _fetch_latest_release(repo: str) -> dict[str, Any]:
    url = f"{GITHUB_API_BASE}/{repo}/releases/latest"
    request = urllib.request.Request(
        url, headers={"User-Agent": "GestaoInteligente-Updater"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def check_for_updates(config_path: Path, current_version: str) -> UpdateCheckResult:
    repo = resolve_repo(config_path)
    if not repo:
        return UpdateCheckResult(
            status="no_repo",
            current_version=current_version,
            message="Repositório não configurado para atualizações.",
        )
    try:
        release = _fetch_latest_release(repo)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            message=f"Não foi possível verificar atualizações ({exc}).",
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
            message="Você já está na versão mais recente.",
        )

    assets = release.get("assets", [])
    download_url = None
    if isinstance(assets, list):
        download_url = _select_asset(assets, latest_version)

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
