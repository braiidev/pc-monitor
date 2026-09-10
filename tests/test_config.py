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
    assert again["general"]["loop"] is False


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
    assert not legacy.exists()  # la vieja se movió
    assert new.exists()  # la nueva nació


def test_migrate_skips_if_new_exists(tmp_path, monkeypatch):
    legacy = tmp_path / "monitor.toml"
    new = tmp_path / "monitor" / "config.toml"
    new.parent.mkdir(parents=True)
    new.write_text("[general]\nloop = true\nshort = false\n")
    legacy.write_text("[general]\nloop = false\n")
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", legacy)
    cfg = config.load_config()
    assert cfg["general"]["loop"] is True  # gana la config nueva
    assert legacy.exists()  # no se tocó la vieja


def test_merge_defaults_missing_section():
    merged = config._deep_merge_defaults({"general": {"top": 3}})
    assert merged["general"]["top"] == 3
    assert merged["general"]["interval"] == 2.0
    assert merged["sections"]["swap"] is True


def test_migrate_old_four_sections_gains_new_toggles(tmp_path, monkeypatch):
    new = tmp_path / "monitor" / "config.toml"
    new.parent.mkdir(parents=True)
    new.write_text(
        "[sections]\ndisk = true\nnetwork = true\nswap = false\nvram = false\n"
    )
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    cfg = config.load_config()
    assert cfg["sections"]["disk"] is True
    assert cfg["sections"]["swap"] is False
    # las claves nuevas caen a sus defaults
    assert cfg["sections"]["ram"] is True
    assert cfg["sections"]["top_procs"] is True
    assert cfg["sections"]["top_cpu"] is True
    assert cfg["sections"]["clock"] is True
    assert cfg["sections"]["decor"] is True


def test_parse_scalar_types():
    assert config._parse_scalar("true") is True
    assert config._parse_scalar("5") == 5
    assert config._parse_scalar("1.5") == 1.5
    assert config._parse_scalar('"clasico"') == "clasico"


@pytest.mark.parametrize(
    "content", ["", "[general]\nthreshold = 2.0", "# solo comentario"]
)
def test_load_tolerates_broken_or_partial(tmp_path, monkeypatch, content):
    new = tmp_path / "monitor" / "config.toml"
    new.parent.mkdir(parents=True)
    new.write_text(content)
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    cfg = config.load_config()
    assert cfg["general"]["loop"] is False
    assert cfg["sections"]["swap"] is True


def test_custom_palette_persists_roundtrip(tmp_path, monkeypatch):
    new = tmp_path / "monitor" / "config.toml"
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    cfg = config.load_config()
    cfg["custom"] = {"red": "196", "yellow": "", "cyan": "38;5;117", "green": "92"}
    config.save_config(cfg)
    again = config.load_config()
    assert again["custom"] == {
        "red": "196",
        "yellow": "",
        "cyan": "38;5;117",
        "green": "92",
    }


def test_written_config_includes_custom_section_with_comments(tmp_path, monkeypatch):
    new = tmp_path / "monitor" / "config.toml"
    monkeypatch.setattr(config, "CONFIG_PATH", new)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    config.load_config()
    text = new.read_text()
    assert "[custom]" in text
    assert "38;5;N" in text  # ejemplo comentado de 256 colores
    config.save_config(config.load_config())


def test_writer_quotes_custom_string_codes(tmp_path):
    cfg = {"custom": {"red": "91", "yellow": "", "cyan": "38;5;117", "green": "92"}}
    text = config._write_toml_lite(cfg)
    assert 'red = "91"' in text
    assert 'yellow = ""' in text
    assert 'cyan = "38;5;117"' in text
