"""Tests de los temas de color (v0.4)."""

from __future__ import annotations

from monitor import theme


def test_exactly_five_themes():
    assert len(theme.THEME_NAMES) == 5
    assert len(theme.THEMES) == 5
    assert set(theme.THEME_NAMES) == set(theme.THEMES)


def test_every_theme_has_all_roles():
    roles = {"bold", "dim", "red", "yellow", "cyan", "green"}
    for t in theme.THEMES.values():
        assert roles <= set(t)


def test_c_resolves_current_theme():
    theme.ACTIVE = "clasico"
    assert theme.c("red") == "\033[91m"
    assert theme.c("reset") == "\033[0m"
    theme.ACTIVE = "mono"
    assert theme.c("red") == ""
    assert theme.c("bold") == "\033[1m"


def test_unknown_role_falls_back_to_reset():
    theme.ACTIVE = "clasico"
    assert theme.c("nope") == "\033[0m"


def test_is_theme():
    assert theme.is_theme("clasico")
    assert theme.is_theme("ocean")
    assert not theme.is_theme("neon")
    assert not theme.is_theme("")


def test_cycle_theme_rotates_and_wraps():
    theme.ACTIVE = "clasico"
    order = list(theme.THEME_NAMES)
    for i in range(len(order)):
        assert theme.ACTIVE == order[i]
        theme.cycle_theme()
    assert theme.ACTIVE == order[0]