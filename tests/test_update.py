"""Tests del self-update vía git (v0.5). No usan red: repos locales en tmp_path."""

from __future__ import annotations

import subprocess

import pytest

from monitor import update


def _git(repo: str, *args: str) -> None:
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True)


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

    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
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

    monkeypatch.setattr(update, "_pip_reinstall", lambda repo: None)  # no re-instalar paquetes en test
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