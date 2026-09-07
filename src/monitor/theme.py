"""Temas de color ANSI para el monitor.

Cada tema define códigos por rol semántico (rojo/alerta, amarillo, cian,
verde, etc.). El tema activo se cambia en vivo (--theme o tecla t en --loop)
sin re-renderizar el dibujo: views.py consulta theme.c(role) en cada salida.
"""

from __future__ import annotations

THEME_NAMES = ("clasico", "mono", "cyber", "forest", "ocean")

THEMES: dict[str, dict[str, str]] = {
    "clasico": {"bold": "1", "dim": "2", "red": "91", "yellow": "93", "cyan": "96", "green": "92"},
    "mono":    {"bold": "1", "dim": "2", "red": "", "yellow": "", "cyan": "", "green": ""},
    "cyber":   {"bold": "1", "dim": "2", "red": "95", "yellow": "96", "cyan": "93", "green": "92"},
    "forest":  {"bold": "1", "dim": "2", "red": "31", "yellow": "93", "cyan": "36", "green": "92"},
    "ocean":   {"bold": "1", "dim": "2", "red": "94", "yellow": "93", "cyan": "96", "green": "36"},
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