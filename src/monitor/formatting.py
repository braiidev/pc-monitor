"""Formateo de unidades y porcentajes."""

from __future__ import annotations


def fmt_size(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_short(n: float) -> str:
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}P"


def fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def fmt_rate(bps: float) -> str:
    return f"{fmt_short(bps)}/s"