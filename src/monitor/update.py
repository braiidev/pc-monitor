"""Self-update vía git (patrón Clock/Player).

El paquete corre desde un clone de git (`install.sh` lo instala editable desde
`~/.local/share/pc-monitor`), así que la raíz del repo es `parents[2]` de este
módulo (monitor/update.py → src → raíz).

La actualización se decide **por commits** (`git rev-list --count HEAD..origin/main`),
no por comparación semántica de versiones: inmune al defasaje entre el contador
de tasks (v0.N) y el semver de producto (X.Y.Z en pyproject).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT = 8
PULL_TIMEOUT = 30


def repo_root() -> str:
    """Raíz del repo git que contiene este paquete (install desde clone)."""
    return str(Path(__file__).resolve().parents[2])


def _git(
    repo: str, args: list[str], timeout: int = GIT_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, timeout=timeout
    )


def _describe(repo: str, rev: str) -> str:
    try:
        r = _git(repo, ["describe", "--tags", rev, "--abbrev=0"])
        if r.returncode == 0:
            return r.stdout.strip()
        s = _git(repo, ["rev-parse", "--short", rev])
        if s.returncode == 0:
            return s.stdout.strip()
    except Exception:
        pass
    return rev[:7]


@dataclass
class UpdateInfo:
    ok: bool
    error: str | None = None
    behind: int = 0
    current: str = ""
    available: str = ""


def check_update(repo: str) -> UpdateInfo:
    """Devuelve cuántos commits está detrás `repo` respecto de origin/main."""
    if not os.path.isdir(os.path.join(repo, ".git")):
        return UpdateInfo(False, "no es un repositorio git")
    try:
        f = _git(repo, ["fetch", "origin"], timeout=GIT_TIMEOUT)
        if f.returncode != 0:
            return UpdateInfo(False, (f.stderr.strip() or "fetch falló"))
        r = _git(repo, ["rev-list", "--count", "HEAD..origin/main"])
        if r.returncode != 0:
            return UpdateInfo(False, (r.stderr.strip() or "rev-list falló"))
        behind = int((r.stdout or "0").strip() or 0)
        return UpdateInfo(
            ok=True,
            behind=behind,
            current=_describe(repo, "HEAD"),
            available=_describe(repo, "origin/main"),
        )
    except FileNotFoundError:
        return UpdateInfo(False, "git no está instalado")
    except Exception as e:  # noqa: BLE001
        return UpdateInfo(False, str(e))


@dataclass
class UpdateResult:
    ok: bool
    message: str


def do_update(repo: str) -> UpdateResult:
    """Aplica la actualización si hay commits detrás. Si falla el pull, resetea."""
    info = check_update(repo)
    if not info.ok:
        return UpdateResult(False, f"No se pudo verificar: {info.error}")
    if info.behind == 0:
        return UpdateResult(True, f"Estás al día ({info.current})")
    pull = _git(repo, ["pull", "--ff-only"], timeout=PULL_TIMEOUT)
    if pull.returncode == 0:
        _pip_reinstall(repo)
        return UpdateResult(True, f"Actualizado a {info.available} — reiniciá")
    reset = _git(repo, ["reset", "--hard", "origin/main"], timeout=15)
    if reset.returncode == 0:
        _pip_reinstall(repo)
        return UpdateResult(
            True, f"Actualizado a {info.available} (historial corregido) — reiniciá"
        )
    return UpdateResult(False, f"Falló el pull: {pull.stderr.strip()}")


def _pip_reinstall(repo: str) -> None:
    """Refresca el paquete editable del venv si el repo corre desde uno."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", repo],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=PULL_TIMEOUT,
        )
    except Exception:
        pass


__all__ = [
    "UpdateInfo",
    "UpdateResult",
    "check_update",
    "do_update",
    "repo_root",
]
