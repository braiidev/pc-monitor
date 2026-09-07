"""Tests del CLI (flags globales, footer y update en loop)."""

from __future__ import annotations

from monitor.main import main
from monitor import views


def test_version(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["monitor", "--version"])
    main()
    out = capsys.readouterr().out
    assert out.startswith("monitor ")


def test_help(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["monitor", "--help"])
    main()
    out = capsys.readouterr().out
    assert "--uninstall" in out
    assert "--version" in out


def test_help_footer_includes_update_key():
    assert "[u] update" in views.HELP_FOOTER


def test_apply_update_updates_when_behind(monkeypatch, capsys):
    from monitor import update

    info = update.UpdateInfo(ok=True, behind=2, current="v0.1", available="v0.2")
    res = update.UpdateResult(True, "Actualizado a v0.2 — reiniciá")
    called = {}

    def fake_check(repo):
        called["check"] = repo
        return info

    def fake_do(repo):
        called["do"] = repo
        return res

    monkeypatch.setattr(update, "check_update", fake_check)
    monkeypatch.setattr(update, "do_update", fake_do)
    monkeypatch.setattr(update, "repo_root", lambda: "/tmp/repo-test")

    views._apply_update()
    out = capsys.readouterr().out
    assert called.get("check") == "/tmp/repo-test"
    assert called.get("do") == "/tmp/repo-test"
    assert "reiniciá" in out


def test_apply_update_noop_when_up_to_date(monkeypatch, capsys):
    from monitor import update

    info = update.UpdateInfo(ok=True, behind=0, current="v0.2", available="v0.2")
    monkeypatch.setattr(update, "check_update", lambda repo: info)
    called = []
    monkeypatch.setattr(update, "do_update", lambda repo: called.append(repo) or update.UpdateResult(True, "x"))
    views._apply_update()
    out = capsys.readouterr().out
    assert "Estás al día" in out
    assert called == []  # no se llamó do_update


def test_apply_update_handles_error(monkeypatch, capsys):
    from monitor import update

    info = update.UpdateInfo(False, error="git no está instalado")
    monkeypatch.setattr(update, "check_update", lambda repo: info)
    views._apply_update()
    out = capsys.readouterr().out
    assert "git no está instalado" in out