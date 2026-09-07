"""Tests del CLI (flags globales y output básico)."""

from __future__ import annotations

from monitor.main import main


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