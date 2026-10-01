"""Tests del self-update vía git (v0.5). No usan red: repos locales en tmp_path."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from monitor import update


def _git(repo: str, *args: str) -> None:
    subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    )


def _commit(repo: str, msg: str = "v2") -> None:
    """Agrega un commit al origin. Toca v.txt porque `git add -A` sobre el
    fixture sin cambios no commitea nada y `check=True` revienta."""
    import pathlib

    f = pathlib.Path(repo) / "v.txt"
    f.write_text(f.read_text() + f"\n{msg}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def git_pair(tmp_path):
    """Crea origin (repo con 1 commit) y work (clone local), ambos sobre tmp_path."""
    origin = tmp_path / "origin"
    work = tmp_path / "work"
    origin.mkdir()
    _git(str(origin), "init", "-q", "-b", "main")
    _git(str(origin), "config", "user.email", "t@t")
    _git(str(origin), "config", "user.name", "t")
    (origin / "v.txt").write_text("v0")
    _git(str(origin), "add", ".")
    _git(str(origin), "commit", "-q", "-m", "v0")

    subprocess.run(
        ["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True
    )
    _git(str(work), "config", "user.email", "t@t")
    _git(str(work), "config", "user.name", "t")
    return str(origin), str(work)


def test_check_update_ok_when_up_to_date(git_pair, monkeypatch):
    origin, work = git_pair
    monkeypatch.setattr(update, "GIT_TIMEOUT", 30)
    info = update.check_update(work)
    assert info.ok
    assert info.behind == 0


def test_check_update_detects_behind(git_pair):
    origin, work = git_pair
    (__import__("pathlib").Path(origin) / "v.txt").write_text("v1")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "v1")
    info = update.check_update(work)
    assert info.ok
    assert info.behind == 1
    assert info.current != info.available


def test_check_update_non_repo():
    info = update.check_update("/tmp/definitely-not-a-repo-xyz")
    assert not info.ok
    assert "no es un repositorio" in info.error


def test_do_update_pulls_ff_only(git_pair, monkeypatch):
    origin, work = git_pair
    (__import__("pathlib").Path(origin) / "v.txt").write_text("v2")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "v2")

    monkeypatch.setattr(
        update, "_pip_reinstall", lambda repo: None
    )  # no re-instalar paquetes en test
    res = update.do_update(work)
    assert res.ok
    assert "Actualizado" in res.message

    info = update.check_update(work)
    assert info.behind == 0
    assert (__import__("pathlib").Path(work) / "v.txt").read_text() == "v2"


def test_do_update_no_news(git_pair, monkeypatch):
    origin, work = git_pair
    monkeypatch.setattr(update, "_pip_reinstall", lambda repo: None)
    res = update.do_update(work)
    assert res.ok
    assert "Estás al día" in res.message


# ── .pinned-python ──
# El pin existe porque `python3 -m venv` deja .venv/bin/python3 -> /usr/bin/python3
# (symlink flotante). Al subir el SO el venv queda con layout de una versión e
# intérprete de otra y monitor muere con ModuleNotFoundError. install.sh guarda acá
# la ruta versionada con la que se creó el venv para no desviarse en la próxima.


def test_pinned_python_sin_archivo_devuelve_none(tmp_path):
    assert update.pinned_python(str(tmp_path)) is None


def test_pinned_python_lee_el_archivo(tmp_path):
    (tmp_path / update.PINNED_FILE).write_text("/usr/bin/python3.14\n")
    assert update.pinned_python(str(tmp_path)) == "/usr/bin/python3.14"


def test_pinned_python_archivo_vacio_devuelve_none(tmp_path):
    (tmp_path / update.PINNED_FILE).write_text("   \n")
    assert update.pinned_python(str(tmp_path)) is None


def _fake_interp(tmp_path, name: str = "python3.14") -> str:
    """Intérprete falso pero ejecutable, para no depender del SO en el test."""
    d = tmp_path / "interps"
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    p.chmod(0o755)
    return str(p)


def test_sync_pinned_escribe_cuando_no_hay_pin(tmp_path):
    exe = _fake_interp(tmp_path)
    viejo = update.sync_pinned_python(str(tmp_path), exe)
    assert viejo == "(ninguno)"
    assert update.pinned_python(str(tmp_path)) == str(
        tmp_path / "interps" / "python3.14"
    )


def test_sync_pinned_no_toca_si_ya_es_el_mismo(tmp_path):
    exe = _fake_interp(tmp_path)
    update.sync_pinned_python(str(tmp_path), exe)
    assert update.sync_pinned_python(str(tmp_path), exe) is None


def test_sync_pinned_corrige_pin_desfasado(tmp_path):
    """El caso del upgrade de SO: el pin apunta a una versión que ya no existe."""
    (tmp_path / update.PINNED_FILE).write_text("/usr/bin/python3.12-QUE-NO-EXISTE\n")
    exe = _fake_interp(tmp_path, "python3.14")
    viejo = update.sync_pinned_python(str(tmp_path), exe)
    assert viejo == "/usr/bin/python3.12-QUE-NO-EXISTE"
    assert update.pinned_python(str(tmp_path)) == str(
        tmp_path / "interps" / "python3.14"
    )


def test_sync_pinned_rechaza_ejecutable_inesperado(tmp_path):
    """Con layout raro preferimos no escribir antes que dejar un pin basura."""
    exe = _fake_interp(tmp_path, "python-real")
    assert update.sync_pinned_python(str(tmp_path), exe) is None
    assert update.pinned_python(str(tmp_path)) is None


def test_sync_pinned_rechaza_interprete_dentro_del_venv(tmp_path, monkeypatch):
    """venv creado con --copies: realpath cae adentro y no sirve como pin."""
    venv = tmp_path / "venv"
    exe = venv / "bin" / "python3.14"
    exe.parent.mkdir(parents=True)
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setattr(sys, "prefix", str(venv))
    assert update.sync_pinned_python(str(tmp_path), str(exe)) is None
    assert update.pinned_python(str(tmp_path)) is None


# ── venv anclado al alias flotante ──
# Un venv sano y uno flotante resuelven a la MISMA ruta (/usr/bin/python3.12), así
# que comparar readlink -f no los distingue. Estos tests construyen las dos
# estructuras a mano para no depender del SO de la máquina.


def _venv(tmp_path, target: str) -> str:
    """Arma <tmp>/repo/.venv/bin/ con bin/python3 → target."""
    repo = tmp_path / "repo"
    binp = repo / ".venv" / "bin"
    binp.mkdir(parents=True)
    os.symlink(target, binp / "python3")
    return str(repo)


def test_venv_is_floating_true(tmp_path):
    """La firma exacta de `python3 -m venv`: cuelga de /usr/bin/python3."""
    usr = tmp_path / "usr" / "bin"
    usr.mkdir(parents=True)
    os.symlink("python3.12", usr / "python3")  # el alias flotante del SO
    repo = _venv(tmp_path, str(usr / "python3"))
    assert update.venv_is_floating(repo) is True


def test_venv_is_floating_false_si_esta_versionado(tmp_path):
    usr = tmp_path / "usr" / "bin"
    usr.mkdir(parents=True)
    real = usr / "python3.12"
    real.write_text("#!/bin/sh\n", encoding="utf-8")
    repo = _venv(tmp_path, "python3.12")
    os.symlink(str(real), os.path.join(repo, ".venv", "bin", "python3.12"))
    assert update.venv_is_floating(repo) is False


def test_venv_is_floating_false_con_copies(tmp_path):
    repo = _venv(tmp_path, "python3.12")
    os.unlink(os.path.join(repo, ".venv", "bin", "python3"))
    with open(os.path.join(repo, ".venv", "bin", "python3"), "w") as f:
        f.write("#!/bin/sh\n")
    assert update.venv_is_floating(repo) is False


def test_venv_is_floating_false_sin_venv(tmp_path):
    assert update.venv_is_floating(str(tmp_path)) is False


def test_run_installer_skipea_si_no_hay_script(tmp_path):
    res = update.run_installer(str(tmp_path))
    assert res.skipped is True
    assert res.ok is False


def _installer(tmp_path, body: str) -> str:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (repo / "install.sh").write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    return str(repo)


def test_run_installer_ok(tmp_path):
    repo = _installer(tmp_path, 'echo corrido > "$PC_MONITOR_DIR/marker"\nexit 0\n')
    res = update.run_installer(repo)
    assert res.ok is True
    assert res.skipped is False
    assert res.rebuilt is False
    assert (tmp_path / "repo" / "marker").read_text().strip() == "corrido"


def test_run_installer_reporta_fallo(tmp_path):
    repo = _installer(tmp_path, 'echo "se rompió" >&2\nexit 1\n')
    res = update.run_installer(repo)
    assert res.ok is False
    assert "se rompió" in res.detail


def test_run_installer_detecta_rebuild(tmp_path):
    """Un venv recreado deja un marker nuevo: eso es lo que se compara.

    (El inode del symlink no sirve: al borrarlo y recrearlo el filesystem
    reutiliza el número y el rebuild pasa inadvertido.)
    """
    repo = _installer(
        tmp_path,
        'mkdir -p "$PC_MONITOR_DIR/.venv/bin"\n'
        'rm -f "$PC_MONITOR_DIR/.venv/bin/python"\n'
        'ln -s python3.12 "$PC_MONITOR_DIR/.venv/bin/python"\n'
        f'date +%s%N > "$PC_MONITOR_DIR/.venv/{update.VENV_MARKER}"\n'
        "exit 0\n",
    )
    bindir = os.path.join(repo, ".venv", "bin")
    os.makedirs(bindir)
    os.symlink("python3.12", os.path.join(bindir, "python"))
    res = update.run_installer(repo)
    assert res.ok is True
    assert res.rebuilt is True
    assert (tmp_path / "repo" / ".venv" / update.VENV_MARKER).exists()


def test_run_installer_no_reporta_rebuild_si_no_cambio(tmp_path):
    repo = _installer(tmp_path, "exit 0\n")
    bindir = os.path.join(repo, ".venv", "bin")
    os.makedirs(bindir)
    os.symlink("python3.12", os.path.join(bindir, "python"))
    res = update.run_installer(repo)
    assert res.ok is True
    assert res.rebuilt is False


def _venv_en(clone: str, tmp_path, floating: bool) -> None:
    """Deja <clone>/.venv/bin/ con la estructura sana o flotante."""
    bindir = os.path.join(clone, ".venv", "bin")
    os.makedirs(bindir, exist_ok=True)
    if not floating:
        os.symlink("python3.12", os.path.join(bindir, "python3"))
        return
    usr = tmp_path / "usr" / "bin"
    usr.mkdir(parents=True, exist_ok=True)
    alias = usr / "python3"
    if not alias.is_symlink():
        os.symlink("python3.12", alias)  # el alias flotante del SO
    os.symlink(str(alias), os.path.join(bindir, "python3"))


_STUB_REPARA = (
    "#!/usr/bin/env bash\n"
    'rm -f "$PC_MONITOR_DIR/.venv/bin/python3" "$PC_MONITOR_DIR/.venv/bin/python"\n'
    'ln -s python3.12 "$PC_MONITOR_DIR/.venv/bin/python3"\n'
    'printf "#!/bin/sh\\n" > "$PC_MONITOR_DIR/.venv/bin/python"\n'
    f'date +%s%N > "$PC_MONITOR_DIR/.venv/{update.VENV_MARKER}"\n'
    "exit 0\n"
)


def test_do_update_repara_venv_flotante_aunque_estea_al_dia(
    git_pair, tmp_path, monkeypatch
):
    monkeypatch.setattr(update, "_pip_reinstall", lambda repo: None)
    """El silencio que motivó esto: 'al día' con el venv sin protección.

    git_pair queda behind=0, así que esto ejercita justo la rama que antes
    respondía "Estás al día" y dejaba el alias flotante puesto.
    """
    _, clone = git_pair
    _venv_en(clone, tmp_path, floating=True)
    with open(os.path.join(clone, "install.sh"), "w", encoding="utf-8") as f:
        f.write(_STUB_REPARA)

    assert update.venv_is_floating(clone) is True
    res = update.do_update(clone)
    assert res.ok is True
    assert "venv recreado" in res.message
    assert update.venv_is_floating(clone) is False


def test_do_update_no_toca_instalador_si_esta_sano_y_al_dia(
    git_pair, tmp_path, monkeypatch
):
    monkeypatch.setattr(update, "_pip_reinstall", lambda repo: None)
    """Sin novedad ni venv flotante, no hace falta reinstallar."""
    _, clone = git_pair
    _venv_en(clone, tmp_path, floating=False)
    calls = tmp_path / "calls"
    with open(os.path.join(clone, "install.sh"), "w", encoding="utf-8") as f:
        f.write(f'#!/usr/bin/env bash\necho x >> "{calls}"\nexit 0\n')

    res = update.do_update(clone)
    assert res.ok is True
    assert "al día" in res.message
    assert not calls.exists()


def test_do_update_siempre_pasa_por_instalador_si_hubo_commits(
    git_pair, tmp_path, monkeypatch
):
    monkeypatch.setattr(update, "_pip_reinstall", lambda repo: None)
    """El código recién bajado puede traer un install.sh distinto: hay que correrlo."""
    origin, clone = git_pair
    _commit(origin, "v2")
    _venv_en(clone, tmp_path, floating=False)
    calls = tmp_path / "calls"
    with open(os.path.join(clone, "install.sh"), "w", encoding="utf-8") as f:
        f.write(f'#!/usr/bin/env bash\necho x >> "{calls}"\nexit 0\n')

    res = update.do_update(clone)
    assert res.ok is True
    assert "Actualizado" in res.message
    assert calls.exists()
