"""Tests del CLI (flags globales, footer, temas y update en loop)."""

from __future__ import annotations

import argparse

import pytest

from monitor.main import main, resolve_theme
from monitor import views
from monitor import config


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
    assert "[u]update" in views.HELP_FOOTER


def test_help_footer_lists_all_toggle_keys():
    for k in views.TOGGLE_KEYS:
        assert f"[{k}]" in views.HELP_FOOTER
    for action in ("m", "c", "t", "?", "q"):
        assert f"[{action}]" in views.HELP_FOOTER


def _ns(theme: str) -> argparse.Namespace:
    return argparse.Namespace(theme=theme)


def test_resolve_theme_keeps_valid(monkeypatch, capsys):
    assert resolve_theme([], _ns("calido"), {}, False) == "calido"


def test_resolve_theme_fallback_from_config(monkeypatch, capsys):
    cfg = {"general": {"theme": "ocean"}}  # tema viejo de otra iteración
    assert resolve_theme([], _ns("ocean"), cfg, False) == "clasico"
    assert cfg["general"]["theme"] == "clasico"  # se corrige la config


def test_resolve_theme_fallback_no_config(monkeypatch, capsys):
    cfg = {"general": {"theme": "ocean"}}
    assert resolve_theme([], _ns("ocean"), cfg, True) == "clasico"
    assert cfg["general"]["theme"] == "ocean"  # no toca la config


def test_resolve_theme_explicit_unknown_raises(monkeypatch, capsys):
    with pytest.raises(SystemExit) as e:
        resolve_theme(["--theme", "nope"], _ns("nope"), {}, False)
    assert e.value.code == 1
    err = capsys.readouterr().err
    assert "Tema desconocido" in err


def test_toast_seconds_positive_and_multi_interval():
    assert views.TOAST_SECONDS >= 2.0  # debe durar al menos un par de refrescos


def test_cli_theme_custom_saves_valid_palette(tmp_path, monkeypatch, capsys):
    from monitor.main import _cli_theme_custom

    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "monitor" / "config.toml")
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    monkeypatch.setattr("os.environ", {"EDITOR": "true"})  # editor que "no edita"
    monkeypatch.setattr("shutil.which", lambda name: None)
    cfg = config.load_config()
    cfg["custom"] = {"red": "196", "yellow": "93", "cyan": "96", "green": "92"}
    config.save_config(cfg)

    rc = _cli_theme_custom()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Tema custom actualizado" in out
    assert "red=196" in out
    again = config.load_config()
    assert again["custom"]["red"] == "196"


def test_cli_theme_custom_normalizes_invalid(tmp_path, monkeypatch, capsys):
    from monitor.main import _cli_theme_custom

    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "monitor" / "config.toml")
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    monkeypatch.setattr("os.environ", {"EDITOR": "true"})
    monkeypatch.setattr("shutil.which", lambda name: None)
    cfg = config.load_config()
    cfg["custom"] = {"red": "pepe", "yellow": "93", "cyan": ";", "green": "92"}
    config.save_config(cfg)

    rc = _cli_theme_custom()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Valores inválidos" in out
    again = config.load_config()
    assert again["custom"]["red"] == "91"  # caen a clasico
    assert again["custom"]["cyan"] == "96"


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
    monkeypatch.setattr(
        update,
        "do_update",
        lambda repo: called.append(repo) or update.UpdateResult(True, "x"),
    )
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
