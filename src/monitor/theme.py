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
    custom          plantilla editable (default = clasico)
"""

from __future__ import annotations

THEME_NAMES = ("clasico", "mono", "calido", "alto_contraste", "flatline", "custom")

THEMES: dict[str, dict[str, str]] = {
    "clasico": {"bold": "1", "dim": "2", "red": "91", "yellow": "93", "cyan": "96", "green": "92"},
    "mono":    {"bold": "1", "dim": "2", "red": "", "yellow": "", "cyan": "", "green": ""},
    "calido":  {"bold": "1", "dim": "2", "red": "91", "yellow": "93", "cyan": "93", "green": "91"},
    "alto_contraste": {"bold": "1", "dim": "2", "red": "95", "yellow": "95", "cyan": "95", "green": "92"},
    "flatline": {"bold": "1", "dim": "2", "red": "91", "yellow": "91", "cyan": "96", "green": "91"},
    "custom":  {"bold": "1", "dim": "2", "red": "91", "yellow": "93", "cyan": "96", "green": "92"},
}

RESET_CODE = "0"

ACTIVE = "clasico"


def c(role: str) -> str:
    """Devuelve la secuencia ANSI del rol en el tema activo ("" si es sin color)."""
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