"""Tests de la config TOML-lite."""

from __future__ import annotations

import pytest

from monitor import config


def test_write_read_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "monitor" / "config.toml")
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    cfg = config.load_config()
    cfg["general"]["top"] = 7
    cfg["sections"]["disk"] = True
    config.save_config(cfg)
    again = config.load_config()
    assert again["general"]["top"] == 7
    assert again["sections"]["disk"] is True
    assert again["general"]["loop"] is True


def test_load_uses_new_path(tmp_path, monkeypatch):
    new = tmp_path / "monitor" / "config.toml"
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    cfg = config.load_config()
    cfg["sections"]["swap"] = False
    config.save_config(cfg)
    assert new.read_text().splitlines()[0] == "[general]"


def test_migrate_legacy_config(tmp_path, monkeypatch):
    legacy = tmp_path / "monitor.toml"
    new = tmp_path / "monitor" / "config.toml"
    legacy.write_text("[general]\nloop = false\n")
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", legacy)
    cfg = config.load_config()
    assert cfg["general"]["loop"] is False
    assert not legacy.exists()          # la vieja se movió
    assert new.exists()                 # la nueva nació


def test_migrate_skips_if_new_exists(tmp_path, monkeypatch):
    legacy = tmp_path / "monitor.toml"
    new = tmp_path / "monitor" / "config.toml"
    new.parent.mkdir(parents=True)
    new.write_text("[general]\nloop = true\nshort = false\n")
    legacy.write_text("[general]\nloop = false\n")
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", legacy)
    cfg = config.load_config()
    assert cfg["general"]["loop"] is True   # gana la config nueva
    assert legacy.exists()                  # no se tocó la vieja


def test_merge_defaults_missing_section():
    merged = config._deep_merge_defaults({"general": {"top": 3}})
    assert merged["general"]["top"] == 3
    assert merged["general"]["interval"] == 2.0
    assert merged["sections"]["swap"] is True


def test_parse_scalar_types():
    assert config._parse_scalar("true") is True
    assert config._parse_scalar("5") == 5
    assert config._parse_scalar("1.5") == 1.5
    assert config._parse_scalar('"clasico"') == "clasico"


@pytest.mark.parametrize("content", ["", "[general]\nthreshold = 2.0", "# solo comentario"])
def test_load_tolerates_broken_or_partial(tmp_path, monkeypatch, content):
    new = tmp_path / "monitor" / "config.toml"
    new.parent.mkdir(parents=True)
    new.write_text(content)
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    cfg = config.load_config()
    assert cfg["general"]["loop"] is True
    assert cfg["sections"]["swap"] is True