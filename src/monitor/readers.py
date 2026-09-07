"""Lectores de /proc y sysfs. No imprimen nada; devuelven datos."""

from __future__ import annotations

import os
from pathlib import Path


def read_meminfo() -> dict[str, int]:
    d: dict[str, int] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split()
            d[parts[0].rstrip(":")] = int(parts[1]) * 1024
    return d


def read_cpu_lines() -> list[str]:
    with open("/proc/stat") as f:
        return [l for l in f if l.startswith("cpu")]


def cpu_pct_from_lines(before: list[str], after: list[str]) -> dict[str, float]:
    """Calcula % de uso por núcleo comparando dos snapshots de /proc/stat."""
    result: dict[str, float] = {}
    b = {l.split()[0]: list(map(int, l.split()[1:])) for l in before}
    a = {l.split()[0]: list(map(int, l.split()[1:])) for l in after}
    for cid, a_parts in a.items():
        b_parts = b.get(cid)
        if not b_parts:
            continue
        total_delta = sum(a_parts) - sum(b_parts)
        idle_delta = (a_parts[3] + a_parts[4]) - (b_parts[3] + b_parts[4])
        result[cid] = (1 - idle_delta / total_delta) * 100 if total_delta else 0.0
    return result


def read_vram() -> list[tuple[str, int, int]]:
    """Devuelve (label, total, usada) por GPU expuesta en sysfs."""
    out: list[tuple[str, int, int]] = []
    for p in sorted(Path("/sys/class/drm").glob("card*/device/mem_info_vram_total")):
        card = p.parent.parent.name
        try:
            total = int(p.read_text().strip())
            used = int(p.parent.joinpath("mem_info_vram_used").read_text().strip())
        except (FileNotFoundError, ValueError, OSError):
            continue
        if total <= 0:
            continue
        out.append((card, total, used))
    return out


def disk_stats() -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}
    try:
        with open("/proc/diskstats") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 10:
                    continue
                name = parts[2]
                if name[-1].isdigit() and not name.startswith("loop"):
                    continue  # ignorar particiones individuales
                if name.startswith(("loop", "ram")):
                    continue
                sectors_read, sectors_written = int(parts[5]), int(parts[9])
                stats[name] = (sectors_read * 512, sectors_written * 512)
    except FileNotFoundError:
        pass
    return stats


def net_stats() -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}
    with open("/proc/net/dev") as f:
        for line in f.readlines()[2:]:
            iface, rest = line.split(":", 1)
            iface = iface.strip()
            if iface == "lo":
                continue
            fields = rest.split()
            rx_bytes, tx_bytes = int(fields[0]), int(fields[8])
            stats[iface] = (rx_bytes, tx_bytes)
    return stats


def _proc_rss(pid: str) -> tuple[int, str] | None:
    try:
        with open(f"/proc/{pid}/status") as f:
            name = "?"
            rss = 0
            for line in f:
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("VmRSS:"):
                    rss = int(line.split(":", 1)[1].strip().split()[0]) * 1024
            return rss, name
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        return None


def read_procs(limit: int = 0) -> list[tuple[int, str, str]]:
    """Devuelve procesos ordenados por RSS descendente. limit=0 -> todos."""
    procs: list[tuple[int, str, str]] = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        info = _proc_rss(pid)
        if info is None:
            continue
        rss, name = info
        procs.append((rss, pid, name))

    procs.sort(reverse=True)
    return procs[:limit] if limit else procs


def cpu_time(pid: str) -> int | None:
    try:
        with open(f"/proc/{pid}/stat") as f:
            parts = f.read().split()
            return int(parts[13]) + int(parts[14])
    except (FileNotFoundError, IndexError, ValueError):
        return None