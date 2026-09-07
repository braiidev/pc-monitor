"""Vistas del monitor: info por sección, vista corta, completa y el modo --loop."""

from __future__ import annotations

import io
import os
import select
import shutil
import sys
import termios
import time

from monitor import formatting as fmt
from monitor import readers
from monitor import theme

# Colores dinámicos: resuelven el código ANSI del tema activo al imprimirse,
# así la tecla "t" puede cambiar el tema en vivo dentro de --loop.
class _ThemeColor(str):
    def __new__(cls, role: str) -> "_ThemeColor":
        obj = super().__new__(cls, "")
        obj.role = role
        return obj

    def __format__(self, spec: str) -> str:
        return format(theme.c(self.role), spec)

    def __str__(self) -> str:  # type: ignore[override]
        return theme.c(self.role)


BOLD = _ThemeColor("bold")
DIM = _ThemeColor("dim")
RED = _ThemeColor("red")
YELLOW = _ThemeColor("yellow")
CYAN = _ThemeColor("cyan")
GREEN = _ThemeColor("green")
RESET = _ThemeColor("reset")


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}── {title} ──{RESET}")


# ────────────────────────── secciones ──────────────────────────

def ram_info(mi: dict[str, int]) -> None:
    total = mi["MemTotal"]
    free = mi["MemFree"]
    avail = mi["MemAvailable"]
    used = total - avail
    section("RAM")
    print(f"  Total:     {fmt.fmt_size(total)}")
    print(f"  Usada:     {fmt.fmt_size(used)}  ({fmt.fmt_pct(used / total * 100)})")
    print(f"  Disponible:{GREEN} {fmt.fmt_size(avail)}{RESET}")
    print(f"  Libre:     {fmt.fmt_size(free)}")


def swap_info(mi: dict[str, int]) -> None:
    total = mi.get("SwapTotal", 0)
    if not total:
        return
    free = mi.get("SwapFree", 0)
    used = total - free
    section("SWAP")
    print(f"  Total: {fmt.fmt_size(total)}")
    print(f"  Usada: {fmt.fmt_size(used)}  ({fmt.fmt_pct(used / total * 100)})")
    print(f"  Libre: {fmt.fmt_size(free)}")


def vram_info() -> None:
    vram = readers.read_vram()
    if not vram:
        return
    section("VRAM")
    for card, total, used in vram:
        label = "dGPU" if total >= 1024 ** 3 else "iGPU"
        print(f"  {card} {label}:")
        print(f"    Total: {fmt.fmt_size(total)}")
        print(f"    Usada: {fmt.fmt_size(used)}  ({fmt.fmt_pct(used / total * 100)})")
        print(f"    Libre: {GREEN}{fmt.fmt_size(total - used)}{RESET}")


def _bar(pct: float) -> tuple[str, str]:
    """Devuelve (bloque coloreado, color) según el porcentaje de uso."""
    color = GREEN if pct < 50 else YELLOW if pct < 80 else RED
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    return bar, color


def cpu_info(sample_seconds: float = 0.2) -> None:
    section("CPU")
    with open("/proc/loadavg") as f:
        load = f.read().strip()
    print(f"  Load: {load}")
    cores = os.cpu_count() or 0
    print(f"  Núcleos: {cores}")

    before = readers.read_cpu_lines()
    time.sleep(sample_seconds)
    after = readers.read_cpu_lines()
    pct_by_core = readers.cpu_pct_from_lines(before, after)

    for cid, use_pct in pct_by_core.items():
        if cid == "cpu":
            continue  # se muestra el agregado por separado abajo
        bar, color = _bar(use_pct)
        print(f"  {cid}: {color}{bar}{RESET} {fmt.fmt_pct(use_pct)}")

    if "cpu" in pct_by_core:
        total_pct = pct_by_core["cpu"]
        _, color = _bar(total_pct)
        print(f"  {DIM}Total: {color}{fmt.fmt_pct(total_pct)}{RESET}")


def disk_info(sample_seconds: float = 0.2) -> None:
    section("DISCO")
    usage = shutil.disk_usage("/")
    used_pct = usage.used / usage.total * 100 if usage.total else 0
    print(f"  / Total:  {fmt.fmt_size(usage.total)}")
    print(f"  / Usado:  {fmt.fmt_size(usage.used)}  ({fmt.fmt_pct(used_pct)})")
    print(f"  / Libre:  {GREEN}{fmt.fmt_size(usage.free)}{RESET}")

    before = readers.disk_stats()
    time.sleep(sample_seconds)
    after = readers.disk_stats()
    for name, (r_after, w_after) in after.items():
        r_before, w_before = before.get(name, (r_after, w_after))
        read_rate = (r_after - r_before) / sample_seconds
        write_rate = (w_after - w_before) / sample_seconds
        if read_rate or write_rate:
            print(f"  {name}: {CYAN}R {fmt.fmt_rate(read_rate)}{RESET}  {YELLOW}W {fmt.fmt_rate(write_rate)}{RESET}")


def network_info(sample_seconds: float = 0.2) -> None:
    section("RED")
    before = readers.net_stats()
    time.sleep(sample_seconds)
    after = readers.net_stats()
    if not after:
        print(f"  {DIM}Sin interfaces activas{RESET}")
        return
    for iface, (rx_after, tx_after) in after.items():
        rx_before, tx_before = before.get(iface, (rx_after, tx_after))
        rx_rate = (rx_after - rx_before) / sample_seconds
        tx_rate = (tx_after - tx_before) / sample_seconds
        print(f"  {iface}: {GREEN}↓ {fmt.fmt_rate(rx_rate)}{RESET}  {YELLOW}↑ {fmt.fmt_rate(tx_rate)}{RESET}")


# ────────────────────────── procesos ──────────────────────────

def print_warning(procs: list[tuple[int, str, str]], threshold_gb: float, threshold_bytes: int) -> None:
    over = [p for p in procs if p[0] >= threshold_bytes]
    if over:
        print(f"\n{RED}{BOLD}⚠  Procesos que exceden {threshold_gb}GB de RAM:{RESET}")
        for rss, pid, name in over:
            print(f"  {RED}{fmt.fmt_size(rss):>8}{RESET}  PID {pid:<6}  {name}")
    else:
        print(f"\n{GREEN}✓ Ningún proceso excede {threshold_gb}GB de RAM.{RESET}")


def show_procs(
    procs: list[tuple[int, str, str]], threshold_gb: float, threshold_bytes: int, limit: int = 5
) -> None:
    if not procs:
        return
    section(f"TOP {limit} RAM")
    for rss, pid, name in procs[:limit]:
        color = RED if rss >= threshold_bytes else ""
        flag = f" {RED}⚠ >{threshold_gb}GB{RESET}" if rss >= threshold_bytes else ""
        print(f"  {color}{fmt.fmt_size(rss):>8}{RESET}  {pid:<6} {name}{flag}")
    print_warning(procs, threshold_gb, threshold_bytes)


def top_processes(
    threshold_gb: float, threshold_bytes: int, limit: int = 5, cpu_sample_seconds: float = 0.1
) -> None:
    procs = readers.read_procs()
    show_procs(procs, threshold_gb, threshold_bytes, limit)

    section("TOP procesos por CPU (sample)")
    candidates = procs[:40]  # limitar el sampleo a los de mayor RSS por costo
    t1 = {pid: readers.cpu_time(pid) for _, pid, _ in candidates}
    time.sleep(cpu_sample_seconds)

    cpu_procs: list[tuple[float, str, str, int]] = []
    for rss, pid, name in candidates:
        before = t1.get(pid)
        after = readers.cpu_time(pid)
        if before is None or after is None:
            continue
        pct = (after - before) / cpu_sample_seconds  # jiffies (1/100s) -> % aprox
        cpu_procs.append((pct, pid, name, rss))
    cpu_procs.sort(reverse=True)

    for pct, pid, name, rss in cpu_procs[:limit]:
        color = RED if rss >= threshold_bytes else ""
        flag = f" {RED}⚠ >{threshold_gb}GB{RESET}" if rss >= threshold_bytes else ""
        print(f"  {color}{fmt.fmt_pct(pct):>7}{RESET}  PID {pid:<6} {name}{flag}")


# ────────────────────────── vistas ──────────────────────────

def full_info(args: object, threshold_bytes: int) -> None:
    mi = readers.read_meminfo()
    ram_info(mi)
    if args.swap:
        swap_info(mi)
    if args.vram:
        vram_info()
    cpu_info()
    if args.disk:
        disk_info()
    if args.network:
        network_info()
    top_processes(args.threshold, threshold_bytes, limit=args.top)
    print()


def short_info(args: object, threshold_bytes: int) -> None:
    tw, _ = shutil.get_terminal_size((40, 20))
    w = min(tw, 40)
    sep = f"{DIM}{'─' * w}{RESET}"
    pr = lambda s: print(s[:w])

    mi = readers.read_meminfo()

    pr(sep)
    total = mi["MemTotal"]
    used = total - mi["MemAvailable"]
    pr(f"  {CYAN}RAM{RESET} {fmt.fmt_short(used):>6}/{fmt.fmt_short(total):<6} {used / total * 100:.1f}%")

    with open("/proc/loadavg") as f:
        load = f.read().strip().split()[0]
    pr(f"  {CYAN}CPU{RESET} {load:>5}  {os.cpu_count() or 0}c")

    if args.swap:
        swap_total = mi.get("SwapTotal", 0)
        if swap_total:
            swap_used = swap_total - mi.get("SwapFree", 0)
            pr(f"  {YELLOW}SWP{RESET} {fmt.fmt_short(swap_used):>6}/{fmt.fmt_short(swap_total):<6} {swap_used / swap_total * 100:.1f}%")

    if args.vram:
        for card, vt, vu in readers.read_vram():
            pr(f"  {DIM}GPU{RESET} {fmt.fmt_short(vu):>6}/{fmt.fmt_short(vt):<6} {vu / vt * 100:.1f}%")

    if args.disk:
        usage = shutil.disk_usage("/")
        pr(f"  {CYAN}DSK{RESET} {fmt.fmt_short(usage.used):>6}/{fmt.fmt_short(usage.total):<6} {usage.used / usage.total * 100:.1f}%")

    if args.network:
        before = readers.net_stats()
        time.sleep(0.2)
        after = readers.net_stats()
        rx = sum(a[0] - before.get(i, a)[0] for i, a in after.items()) / 0.2
        tx = sum(a[1] - before.get(i, a)[1] for i, a in after.items()) / 0.2
        pr(f"  {CYAN}NET{RESET} ↓{fmt.fmt_short(rx)}/s ↑{fmt.fmt_short(tx)}/s")

    procs = readers.read_procs(10)

    pr(sep)
    for rss, _, name in procs[:3]:
        txt = f"  {fmt.fmt_short(rss):>6}  {name}"[: w - 2]
        print(f" {'':1}{RED}{txt}{RESET}" if rss >= threshold_bytes else f" {'':1}{txt}")

    pr(sep)
    over = sum(1 for p in procs if p[0] >= threshold_bytes)
    pr(f"  >{args.threshold}GB: {over} proc")


TOGGLE_KEYS = {
    "1": ("short", "Vista corta"),
    "2": ("disk", "Disco"),
    "3": ("network", "Red"),
    "4": ("swap", "Swap"),
    "5": ("vram", "VRAM"),
}

HELP_FOOTER = "[q] salir  [1] vista  [2] disco  [3] red  [4] swap  [5] vram  [t] tema  [u] update  [?] ayuda"


def _apply_update() -> bool:
    """Aplica una actualización (tecla u). Devuelve True si hubo cambios y hay que re-ejecutar."""
    from monitor.update import check_update, do_update, repo_root

    info = check_update(repo_root())
    if not info.ok:
        print(f"⚠ No se pudo verificar: {info.error}")
        return False
    if info.behind == 0:
        print(f"✓ Estás al día ({info.current})")
        return False
    res = do_update(repo_root())
    print(res.message)
    return res.ok


def _restart_process(fd: int, old: object) -> None:
    """Re-ejecuta el proceso (tras una actualización): restaura terminal y execv."""
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        pass
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, "-m", "monitor", *sys.argv[1:]])


def loop_mode(args: object, threshold_bytes: int) -> None:
    if not sys.stdin.isatty():
        print("El modo --loop requiere una terminal.", file=sys.stderr)
        sys.exit(1)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ECHO | termios.ICANON)
    new[6][termios.VMIN] = 0
    new[6][termios.VTIME] = 1

    show_help = False

    def render() -> None:
        buf = io.StringIO()
        old_out = sys.stdout
        sys.stdout = buf
        try:
            tw, th = shutil.get_terminal_size()
            pad = max(0, (th - 12) // 2)
            if args.short:
                short_info(args, threshold_bytes)
            else:
                full_info(args, threshold_bytes)
            if show_help:
                sys.stdout.write(f"\n{DIM}{HELP_FOOTER}{RESET}\n")
            sys.stdout.write(f"{DIM}[u] update  [t] tema  [?] ayuda  {time.strftime('%H:%M')}{RESET}")
        finally:
            sys.stdout = old_out

        content = buf.getvalue()
        lines = content.rstrip("\n").split("\n")
        out = ["\033[H"]
        out.extend("\033[K\n" for _ in range(pad))
        out.extend(f"{l}\033[K\n" for l in lines)
        out.append("\033[J")
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        while True:
            render()
            deadline = time.monotonic() + args.interval
            while time.monotonic() < deadline:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not r:
                    continue
                k = sys.stdin.read(1)
                if k in ("q", "\x1b"):
                    return
                if k in ("?", "h"):
                    show_help = not show_help
                    render()
                    continue
                if k == "t":
                    theme.cycle_theme()
                    args.theme = theme.ACTIVE
                    if not args.no_config:
                        from monitor.config import config_from_args, save_config

                        save_config(config_from_args(args))
                    render()  # feedback inmediato con el nuevo tema
                    continue
                if k == "u":
                    if _apply_update():
                        _restart_process(fd, old)
                        return
                    render()
                    continue
                if k in TOGGLE_KEYS:
                    attr, _label = TOGGLE_KEYS[k]
                    setattr(args, attr, not getattr(args, attr))
                    if not args.no_config:
                        from monitor.config import config_from_args, save_config

                        save_config(config_from_args(args))
                    render()  # feedback inmediato, no esperar al próximo ciclo
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()