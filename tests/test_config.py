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


def test_default_align_is_left(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "monitor" / "config.toml")
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    assert config.load_config()["general"]["align"] == "left"


def test_config_from_args_includes_align(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "monitor" / "config.toml")
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", tmp_path / "monitor.toml")
    args = type(
        "A",
        (),
        {
            "loop": False,
            "short": True,
            "threshold": 1.0,
            "top": 5,
            "interval": 2.0,
            "align": "right",
            "theme": "clasico",
            "ram": True,
            "cpu": True,
            "swap": True,
            "vram": True,
            "disk": False,
            "network": False,
            "top_procs": True,
            "top_cpu": True,
            "clock": True,
            "decor": True,
        },
    )()
    out = config.config_from_args(args)
    assert out["general"]["align"] == "right"


def test_writer_serializes_align(tmp_path):
    cfg = config._deep_merge_defaults({})
    assert 'align = "left"' in config._write_toml_lite(cfg)


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


# ── Un cfg parcial no puede borrar la config del usuario ──
# `_write_toml_lite` saltea las claves ausentes del dict. Eso convertía un cfg
# parcial en una=config truncada`: las secciones quedaban vacías y el usuario
# perdía todo lo que tenía. El archivoobserved era exactamente
# `_write_toml_lite({"general": {"theme": "clasico"}, "sections": {}, "custom": {}})`.


def test_save_config_con_cfg_parcial_no_trunca(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    config.save_config({"general": {"theme": "clasico"}})
    raw = (tmp_path / "config.toml").read_text()
    for section in ("[general]", "[sections]", "[custom]"):
        assert section in raw
    assert "disk = " in raw
    assert "red = " in raw
    assert len(config.parse_toml_lite(raw)["sections"]) == len(
        config.DEFAULT_CONFIG["sections"]
    )


def test_save_config_respeta_lo_que_vene_presente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    config.save_config({"general": {"theme": "clasico"}, "sections": {"disk": True}})
    parsed = config.parse_toml_lite((tmp_path / "config.toml").read_text())
    assert parsed["general"]["theme"] == "clasico"
    assert parsed["sections"]["disk"] is True
    # lo no tocado vuelve al default, no a "ausente"
    assert parsed["sections"]["ram"] is True


def test_fill_missing_no_muta_el_entrada(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    original = {"general": {"theme": "oscuro"}}
    config.save_config(original)
    assert set(original["general"]) == {"theme"}
    assert "sections" not in original
