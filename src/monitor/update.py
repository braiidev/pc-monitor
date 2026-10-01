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

# Nombre del archivo donde install.sh persiste la ruta versionada del intérprete
# con la que se creó el venv. Ver install.sh para el porqué (symlink flotante).
PINNED_FILE = ".pinned-python"

# install.sh escribe esto dentro del venv cada vez que lo recrea. Comparar el valor
# antes y después del update es la forma determinista de saber si este proceso quedó
# apuntando a un árbol que ya no existe.
VENV_MARKER = ".created-at"


def repo_root() -> str:
    """Raíz del repo git que contiene este paquete (install desde clone)."""
    return str(Path(__file__).resolve().parents[2])


def pinned_python(repo: str | None = None) -> str | None:
    """Ruta del intérprete pineado por install.sh, o None si no hay pin."""
    try:
        raw = (Path(repo or repo_root()) / PINNED_FILE).read_text().strip()
    except OSError:
        return None
    return raw or None


def sync_pinned_python(repo: str | None = None, exe: str | None = None) -> str | None:
    """Realinea `.pinned-python` con el intérprete que realmente está corriendo.

    Si el venv se rehizo a mano (o install.sh corrió en otra máquina), el pin queda
    mintiendo y eso termina en el ModuleNotFoundError del upgrade de SO. Devuelve el
    valor anterior si hubo que corregirlo, None si ya estaba bien o si el layout es
    inesperado (preferimos no escribir antes que dejar un pin basura).
    """
    base = Path(repo or repo_root())
    candidate = os.path.realpath(exe or sys.executable)
    if not os.path.basename(candidate).startswith("python3"):
        return None
    if str(Path(sys.prefix).resolve()) in candidate:
        return None  # venv con --copies: no sirve como pin
    old = pinned_python(str(base))
    if old == candidate:
        return None
    try:
        (base / PINNED_FILE).write_text(candidate + "\n")
    except OSError:
        return None
    return old or "(ninguno)"


def venv_is_floating(repo: str | None = None) -> bool:
    """¿El venv del repo cuelga del alias flotante /usr/bin/python3?

    Espejo en Python de `venv_flota()` en install.sh. Hace falta acá porque
    `monitor --update` tiene que decidir si repara, y comparar la ruta resuelta no
    sirve: un venv flotante resuelve a la misma ruta que uno sano. Solo la estructura
    del enlace delata el problema.

    Un venv con --copies no tiene symlink en bin/python3: se considera estable.
    """
    base = Path(repo or repo_root()) / ".venv" / "bin"
    try:
        target = os.readlink(base / "python3")
    except OSError:
        return False  # --copies, o no hay venv
    resolved = target if target.startswith("/") else str(base / target)
    return Path(resolved).is_symlink() and os.path.basename(resolved) == "python3"


@dataclass
class InstallRun:
    """Resultado de reejecutar el install.sh del repo."""

    ok: bool
    rebuilt: bool = False
    skipped: bool = False
    detail: str = ""


def _venv_marker(repo: str) -> str:
    try:
        return Path(repo, ".venv", VENV_MARKER).read_text().strip()
    except OSError:
        return ""


def run_installer(
    repo: str, timeout: int = PULL_TIMEOUT, extra_env: dict[str, str] | None = None
) -> InstallRun:
    """Reejecuta el install.sh del repo y deja el entorno en estado canónico.

    do_update no sabe construir un venv: no tiene las reglas de pin, ni el wrapper,
    ni el smoke test. Delega en install.sh, que es la fuente única de cómo se arma el
    entorno, así `monitor --update` deja el sistema exactamente como lo dejaría
    `curl | bash`.

    Ojo: install.sh puede borrar y recrear el .venv desde el que corre este proceso.
    Por eso se reporta `rebuilt`: el llamador tiene que pedir reinicio.
    """
    script = os.path.join(repo, "install.sh")
    if not os.path.isfile(script):
        return InstallRun(False, skipped=True, detail="install.sh no está en el repo")
    before = _venv_marker(repo)
    env = dict(os.environ, PC_MONITOR_DIR=repo)
    env.update(extra_env or {})
    try:
        r = subprocess.run(
            ["bash", script],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return InstallRun(False, detail="install.sh tardó demasiado")
    except OSError as e:  # noqa: BLE001
        return InstallRun(False, detail=str(e))
    if r.returncode != 0:
        return InstallRun(False, detail=(r.stderr or r.stdout).strip()[-400:])
    return InstallRun(True, rebuilt=_venv_marker(repo) != before)


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


def _cerrar(repo: str, base_msg: str, force: bool) -> UpdateResult:
    """Deja el entorno canónico y arma el mensaje final del update.

    Con `force` (hubo commits) siempre reejecuta install.sh, porque el código recién
    bajado puede traer un install.sh distinto. Sin `force` solo corre si el venv está
    anclado al alias flotante, para no reinstallar en cada update sin novedad — pero
    ese chequeo es el que evita el silencio: sin él, un `monitor --update` sobre un venv
    flotante respondía "Estás al día" mientras la protección contra el próximo upgrade
    de SO seguía sin aplicarse.
    """
    if not force and not venv_is_floating(repo):
        return UpdateResult(True, base_msg + " — reiniciá")

    # install.sh solo refresca el paquete editable cuando recrea el venv, así que el
    # refresco se hace acá para no perderlo en el camino de "venv sano".
    _pip_reinstall(repo)

    inst = run_installer(repo)
    if inst.skipped:
        return UpdateResult(True, base_msg + " — reiniciá")
    if not inst.ok:
        return UpdateResult(
            False,
            f"{base_msg} — pero el entorno no quedó sano: {inst.detail}. "
            f"Reejecutá:  bash {os.path.join(repo, 'install.sh')}",
        )
    if inst.rebuilt:
        return UpdateResult(
            True, base_msg + " — venv recreado con ruta versionada, reiniciá monitor"
        )
    return UpdateResult(True, base_msg + " — reiniciá")


def do_update(repo: str) -> UpdateResult:
    """Aplica la actualización si hay commits detrás y deja el entorno sano.

    Si el pull falla por historial divergido, resetea a origin/main. Al final siempre
    pasa por install.sh para que el venv quede anclado a una ruta versionada del
    intérprete: uno anclado a /usr/bin/python3 se rompe solo con el próximo upgrade
    del SO, y acá es el momento de cheapo.
    """
    info = check_update(repo)
    if not info.ok:
        return UpdateResult(False, f"No se pudo verificar: {info.error}")
    if info.behind == 0:
        stale = sync_pinned_python(repo)
        base = f"Estás al día ({info.current})"
        if stale:
            base += f" — intérprete pineado corregido (era {stale})"
        return _cerrar(repo, base, force=False)
    pull = _git(repo, ["pull", "--ff-only"], timeout=PULL_TIMEOUT)
    if pull.returncode == 0:
        return _cerrar(repo, f"Actualizado a {info.available}", force=True)
    reset = _git(repo, ["reset", "--hard", "origin/main"], timeout=15)
    if reset.returncode == 0:
        return _cerrar(
            repo, f"Actualizado a {info.available} (historial corregido)", force=True
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
    "VENV_MARKER",
    "InstallRun",
    "UpdateInfo",
    "UpdateResult",
    "check_update",
    "do_update",
    "pinned_python",
    "repo_root",
    "run_installer",
    "sync_pinned_python",
    "venv_is_floating",
]
