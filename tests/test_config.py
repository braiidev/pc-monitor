"""Tests de la config TOML-lite."""

from __future__ import annotations

from monitor import config


def test_write_read_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "monitor.toml")
    cfg = config.load_config()
    cfg["general"]["top"] = 7
    cfg["sections"]["disk"] = True
    config.save_config(cfg)
    again = config.load_config()
    assert again["general"]["top"] == 7
    assert again["sections"]["disk"] is True
    assert again["general"]["loop"] is True


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