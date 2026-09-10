"""Tests de render: helpers ANSI/flex-wrap y las vistas."""

from __future__ import annotations

from monitor import views


def test_vis_len_ignores_ansi():
    assert views.vis_len(f"{views.CYAN}RAM{views.RESET} 1.2G") == 8


def test_vis_len_plain():
    assert views.vis_len("hola mundo") == 10


def test_flex_wrap_single_line():
    blocks = ["aaaa", "bbbb"]
    assert views.flex_wrap(blocks, 20) == ["aaaa  bbbb"]


def test_flex_wrap_wraps_when_exceeds():
    blocks = ["aaaaaaaa", "bbbbbbbb", "cccccccc"]
    lines = views.flex_wrap(blocks, 20)
    assert len(lines) == 2
    assert lines[0] == "aaaaaaaa  bbbbbbbb"
    assert lines[1] == "cccccccc"


def test_flex_wrap_keeps_wide_block_intact():
    lines = views.flex_wrap(["x" * 30], 10)
    assert lines == ["x" * 30]


def test_flex_wrap_ansi_width_correct():
    blocks = [f"{views.CYAN}RAM{views.RESET}", "cc"]
    assert views.flex_wrap(blocks, 8) == [f"{views.CYAN}RAM{views.RESET}  cc"]
    assert views.flex_wrap(blocks, 6) == [f"{views.CYAN}RAM{views.RESET}", "cc"]


def test_divider_with_centers_text():
    d = views.divider_with(10, "xx")
    assert views.vis_len(d) == 10
    assert "xx" in d


def test_divider_with_empty_is_plain():
    d = views.divider_with(10)
    assert views.vis_len(d) == 10
    assert "─" in d


def test_short_info_prints_wrapped_rows(capsys):
    args = type(
        "A",
        (),
        {
            "ram": True,
            "cpu": True,
            "swap": False,
            "vram": False,
            "disk": False,
            "network": False,
        },
    )()
    views.short_info(args, int(1.0 * 1024**3), footer="14:32")
    out = capsys.readouterr().out
    assert "MONITOR" in out
    assert "14:32" in out
