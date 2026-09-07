"""Tests de los temas de color (v0.4)."""

from __future__ import annotations

from monitor import theme


def test_exactly_five_themes():
    assert len(theme.THEME_NAMES) == 6
    assert len(theme.THEMES) == 6
    assert set(theme.THEME_NAMES) == set(theme.THEMES)


def test_expected_theme_names():
    expected = ("clasico", "mono", "calido", "alto_contraste", "flatline", "custom")
    assert theme.THEME_NAMES == expected
    assert theme.is_theme("alto_contraste")
    assert not theme.is_theme("cyber")


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
    assert theme.is_theme("flatline")
    assert theme.is_theme("custom")
    assert not theme.is_theme("neon")
    assert not theme.is_theme("")


def test_cycle_theme_rotates_and_wraps():
    theme.ACTIVE = "clasico"
    order = list(theme.THEME_NAMES)
    for i in range(len(order)):
        assert theme.ACTIVE == order[i]
        theme.cycle_theme()
    assert theme.ACTIVE == order[0]


def test_themes_are_visually_distinct():
    """Los temas distintivos (todos menos custom, que es plantilla) deben diferir entre sí."""
    before = theme.ACTIVE
    try:
        theme.ACTIVE = "clasico"
        assert theme.c("red") == "\033[91m"
        theme.ACTIVE = "calido"
        assert theme.c("cyan") == "\033[93m"   # estructura amarilla
        assert theme.c("green") == "\033[91m"  # OK rojizo
        theme.ACTIVE = "alto_contraste"
        assert theme.c("cyan") == "\033[95m"   # magenta por todas partes
        theme.ACTIVE = "flatline"
        assert theme.c("cyan") == "\033[96m"   # cian puro
        theme.ACTIVE = "custom"
        assert theme.c("red") == "\033[91m"    # plantilla = clasico
    finally:
        theme.ACTIVE = before

    role_sets = {name: tuple(theme.THEMES[name][r] for r in ("red", "yellow", "cyan", "green")) for name in theme.THEME_NAMES}
    seen: set[tuple[str, ...]] = set()
    for name in theme.THEME_NAMES:
        if name == "custom":
            continue  # plantilla editable, puede coincidir con clasico
        assert role_sets[name] not in seen, f"tema {name} duplica colores de otro"
        seen.add(role_sets[name])


def test_mono_has_no_color_codes():
    theme.ACTIVE = "mono"
    for role in ("red", "yellow", "cyan", "green"):
        assert theme.c(role) == ""