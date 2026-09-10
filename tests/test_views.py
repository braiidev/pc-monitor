"""Tests de render: helpers ANSI/flex-wrap y las vistas."""

from __future__ import annotations

import re
import time

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


def _mini_args(decor: bool = True, clock: bool = True) -> object:
    return type(
        "A",
        (),
        {
            "ram": True,
            "cpu": False,
            "swap": False,
            "vram": False,
            "disk": False,
            "network": False,
            "top_procs": False,
            "top_cpu": False,
            "decor": decor,
            "clock": clock,
        },
    )()


def test_build_footer_help_overrides_clock():
    footer = views._build_footer(True, 0.0, False, "clasico")
    assert views.HELP_FOOTER in footer
    assert not re.search(r"\b\d{2}:\d{2}\b", footer)


def test_build_footer_clock_off_is_empty():
    assert views._build_footer(False, 0.0, False, "clasico") == ""


def test_build_footer_clock_on_shows_time():
    footer = views._build_footer(False, 0.0, True, "clasico")
    assert re.search(r"\d{2}:\d{2}", footer) is not None


def test_build_footer_toast_without_clock_omits_time():
    footer = views._build_footer(False, time.monotonic() + 10, False, "clasico")
    assert "theme: clasico" in footer
    assert not re.search(r"\b\d{2}:\d{2}\b", footer)


def test_short_info_decor_off_keeps_data_and_clock(capsys):
    views.short_info(_mini_args(decor=False), int(1.0 * 1024**3), footer="14:32")
    out = capsys.readouterr().out
    assert "14:32" in out
    assert "MONITOR" not in out
    assert "──" not in out


def test_full_info_decor_off_keeps_data_and_clock(capsys):
    views.full_info(_mini_args(decor=False), int(1.0 * 1024**3), footer="14:32")
    out = capsys.readouterr().out
    assert "14:32" in out
    assert "MONITOR" not in out
    assert "──" not in out


def _top_args(top: int = 3, top_procs: bool = True, top_cpu: bool = False) -> object:
    return type(
        "A",
        (),
        {
            "ram": False,
            "cpu": False,
            "swap": False,
            "vram": False,
            "disk": False,
            "network": False,
            "top_procs": top_procs,
            "top_cpu": top_cpu,
            "decor": False,
            "top": top,
        },
    )()


FAKE_PROCS = [(800 - i * 10, f"p{i}", f"proc{i}") for i in range(6)]


def test_full_top_ram_respects_args_top(monkeypatch, capsys):
    monkeypatch.setattr(views.readers, "read_procs", lambda limit=0: FAKE_PROCS)
    views.full_info(_top_args(top=2), int(1.0 * 1024**3))
    out = capsys.readouterr().out
    assert "proc0" in out and "proc1" in out
    assert "proc2" not in out


def test_short_top_ram_respects_args_top(monkeypatch, capsys):
    monkeypatch.setattr(views.readers, "read_procs", lambda limit=0: FAKE_PROCS[:limit])
    views.short_info(_top_args(top=2), int(1.0 * 1024**3))
    out = capsys.readouterr().out
    assert "proc0" in out and "proc1" in out
    assert "proc2" not in out


def test_full_top_cpu_respects_args_top(monkeypatch, capsys):
    monkeypatch.setattr(views.readers, "read_procs", lambda limit=0: FAKE_PROCS)
    monkeypatch.setattr(
        views.readers, "cpu_time", lambda pid: int(str(pid)[1:])  # p0..p5 -> 0..5
    )
    views.full_info(_top_args(top=2, top_procs=False, top_cpu=True), int(1.0 * 1024**3))
    out = capsys.readouterr().out
    assert "proc5" in out and "proc4" in out  # top 2 por CPU (orden desc)
    assert "proc3" not in out
    assert "proc2" not in out
