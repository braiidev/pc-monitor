"""Temas de color ANSI para el monitor.

Portados de Clock/Player (braiidev/clock -> braiidev/player), adaptados a los
roles de pc-monitor (rojo/alerta, amarillo, cian/estructura, verde/OK).

Identidad de cada tema (tabla COLOR_SPEC de Player):
    tema            cian(estructura)  verde(OK)   amarillo  rojo(alerta)
    clasico         Cian              Verde       Amarillo  Rojo
    mono            (sin color)       (sin color) (sin)     (sin)
    calido          Amarillo          Rojo        Amarillo  Rojo
    alto_contraste  Magenta           Verde       Magenta   Magenta
    flatline        Cian              Rojo        Rojo      Rojo
    custom          editable (default = clasico, vía config [custom] o --theme-custom)
"""

from __future__ import annotations

import re

THEME_NAMES = ("clasico", "mono", "calido", "alto_contraste", "flatline", "custom")

THEMES: dict[str, dict[str, str]] = {
    "clasico": {
        "bold": "1",
        "dim": "2",
        "red": "91",
        "yellow": "93",
        "cyan": "96",
        "green": "92",
    },
    "mono": {"bold": "1", "dim": "2", "red": "", "yellow": "", "cyan": "", "green": ""},
    "calido": {
        "bold": "1",
        "dim": "2",
        "red": "91",
        "yellow": "93",
        "cyan": "93",
        "green": "91",
    },
    "alto_contraste": {
        "bold": "1",
        "dim": "2",
        "red": "95",
        "yellow": "95",
        "cyan": "95",
        "green": "92",
    },
    "flatline": {
        "bold": "1",
        "dim": "2",
        "red": "91",
        "yellow": "91",
        "cyan": "96",
        "green": "91",
    },
    "custom": {
        "bold": "1",
        "dim": "2",
        "red": "91",
        "yellow": "93",
        "cyan": "96",
        "green": "92",
    },
}

RESET_CODE = "0"

ACTIVE = "clasico"

# roles configurables del tema custom (config [custom] / --theme-custom)
CUSTOM_ROLES = ("red", "yellow", "cyan", "green")

# paleta efectiva del tema custom (default = clasico si no está cargada desde config)
_custom_palette: dict[str, str] = {}

_VALID_CODE = re.compile(r"^(\d+)(;\d+)*$")


def valid_code(code: object) -> bool:
    """Valida un código ANSI SGR: vacío (sin color) o números separados por ';' (0-255)."""
    if code is None:
        return False
    raw = str(code).strip()
    if raw == "":
        return True
    if not _VALID_CODE.fullmatch(raw):
        return False
    return all(0 <= int(part) <= 255 for part in raw.split(";"))


def set_custom_palette(palette: dict[str, object]) -> None:
    """Carga la paleta custom desde config; roles inválidos caen a clasico."""
    global _custom_palette
    base = THEMES["clasico"]
    _custom_palette = {}
    for role in CUSTOM_ROLES:
        code = palette.get(role, base[role])
        _custom_palette[role] = (
            str(code).strip().strip('"') if valid_code(code) else base[role]
        )


def custom_palette() -> dict[str, str]:
    """Paleta custom efectiva (la que usa c() cuando ACTIVE == 'custom')."""
    base = THEMES["clasico"]
    return {role: _custom_palette.get(role, base[role]) for role in CUSTOM_ROLES}


def c(role: str) -> str:
    """Devuelve la secuencia ANSI del rol en el tema activo ("" si es sin color)."""
    if ACTIVE == "custom":
        code = custom_palette().get(role, THEMES["custom"].get(role, RESET_CODE))
    else:
        code = THEMES[ACTIVE].get(role, RESET_CODE)
    return f"\033[{code}m" if code else ""


def is_theme(name: str) -> bool:
    return name in THEME_NAMES


def cycle_theme() -> str:
    """Rota al siguiente tema (wrap-around); deja ACTIVE actualizado y lo devuelve."""
    global ACTIVE
    i = THEME_NAMES.index(ACTIVE)
    ACTIVE = THEME_NAMES[(i + 1) % len(THEME_NAMES)]
    return ACTIVE
