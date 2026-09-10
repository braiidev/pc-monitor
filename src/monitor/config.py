"""Configuración TOML-lite del monitor (sin dependencias externas)."""

from __future__ import annotations

import os
import re
from pathlib import Path

CONFIG_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    / "monitor"
    / "config.toml"
)
LEGACY_CONFIG_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    / "monitor.toml"
)

DEFAULT_CONFIG = {
    "general": {
        "loop": True,
        "short": True,
        "threshold": 1.0,
        "top": 5,
        "interval": 2.0,
        "theme": "clasico",
    },
    "sections": {
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
    "custom": {
        "red": "91",
        "yellow": "93",
        "cyan": "96",
        "green": "92",
    },  # = paleta clasico
}

# orden fijo para que el archivo escrito quede siempre legible/estable
_CONFIG_LAYOUT = {
    "general": ["loop", "short", "threshold", "top", "interval", "theme"],
    "sections": [
        "ram",
        "cpu",
        "swap",
        "vram",
        "disk",
        "network",
        "top_procs",
        "top_cpu",
        "clock",
        "decor",
    ],
    "custom": ["red", "yellow", "cyan", "green"],
}

# comentarios volcados siempre en la sección [custom] (el parser los ignora)
_CUSTOM_COMMENTS = """\
# Tema personalizado (editá con: monitor --theme-custom)
# Roles: red (alerta)  yellow (aviso)  cyan (estructura)  green (OK)
# Color = código ANSI, o vacío = sin color. Códigos válidos:
#   31 rojo  32 verde  33 amarillo  34 azul  35 magenta  36 cian  37 blanco
#   brillantes "90".."97"  (ej. 91 rojo claro, 92 verde claro, 96 cian claro)
#   256 colores: "38;5;N"  (N de 0 a 255, ej. 38;5;136)
# Ejemplos: red = "196"   yellow = ""   green = "92"   cyan = "38;5;117"
"""


def _parse_scalar(raw: str) -> object:
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    try:
        return float(raw)
    except ValueError:
        return raw.strip("\"'")


def parse_toml_lite(text: str) -> dict[str, dict[str, object]]:
    cfg: dict[str, dict[str, object]] = {}
    section = None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            cfg.setdefault(section, {})
            continue
        if "=" not in line or section is None:
            continue
        key, _, val = line.partition("=")
        cfg[section][key.strip()] = _parse_scalar(val)
    return cfg


def _write_toml_lite(cfg: dict[str, dict[str, object]]) -> str:
    lines = []
    for section, keys in _CONFIG_LAYOUT.items():
        lines.append(f"[{section}]")
        if section == "custom":
            lines.append(_CUSTOM_COMMENTS.rstrip("\n"))
        for key in keys:
            if key not in cfg.get(section, {}):
                continue
            val = cfg[section][key]
            if isinstance(val, bool):
                val_str = "true" if val else "false"
            elif isinstance(val, str):
                val_str = f'"{val}"'  # strings siempre entre comillas (colores ANSI)
            else:
                val_str = str(val)
            lines.append(f"{key} = {val_str}")
        lines.append("")
    return "\n".join(lines)


def _deep_merge_defaults(
    cfg: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for section, keys in DEFAULT_CONFIG.items():
        merged[section] = {**keys, **cfg.get(section, {})}
    return merged


def _migrate_legacy() -> None:
    """Migra la config vieja en ~/.config/monitor.toml a ~/.config/monitor/config.toml."""
    if CONFIG_PATH.exists() or not LEGACY_CONFIG_PATH.exists():
        return
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(LEGACY_CONFIG_PATH.read_text())
        LEGACY_CONFIG_PATH.unlink()
    except OSError:
        pass  # si no se puede migrar, se regenera la config por defecto al cargar


def load_config() -> dict[str, dict[str, object]]:
    _migrate_legacy()
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(_write_toml_lite(DEFAULT_CONFIG))
        return {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
    try:
        raw = parse_toml_lite(CONFIG_PATH.read_text())
    except OSError:
        raw = {}
    return _deep_merge_defaults(raw)


def save_config(cfg: dict[str, dict[str, object]]) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(_write_toml_lite(cfg))
    except OSError:
        pass  # no interrumpir el monitor por un problema de disco al guardar preferencias


def config_from_args(args: object) -> dict[str, dict[str, object]]:
    from monitor import theme

    return {
        "general": {
            "loop": args.loop,
            "short": args.short,
            "threshold": args.threshold,
            "top": args.top,
            "interval": args.interval,
            "theme": args.theme,
        },
        "sections": {
            "ram": args.ram,
            "cpu": args.cpu,
            "swap": args.swap,
            "vram": args.vram,
            "disk": args.disk,
            "network": args.network,
            "top_procs": args.top_procs,
            "top_cpu": args.top_cpu,
            "clock": args.clock,
            "decor": args.decor,
        },
        "custom": dict(theme.custom_palette()),
    }
