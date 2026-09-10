"""Vistas del monitor: info por sección, vista corta, completa y el modo en vivo (--live)."""

from __future__ import annotations

import io
import os
import re
import select
import shutil
import sys
import termios
import time

from monitor import formatting as fmt
from monitor import readers
from monitor import theme

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def vis_len(s: str) -> int:
    """Largo visible de un string con códigos ANSI (los escapes no cuentan)."""
    return len(_ANSI.sub("", s))


def flex_wrap(blocks: list[str], tw: int, gap: int = 2) -> list[str]:
    """Acomoda bloques de ancho variable en líneas de `tw` cols, con `gap` de separación.
    Un bloque más ancho que `tw` se mantiene entero (nunca se corta a mitad de ANSI)."""
    lines: list[str] = []
    line: list[str] = []
    used = 0
    for b in blocks:
        bw = vis_len(b)
        if line and used + gap + bw > tw:
            lines.append((" " * gap).join(line))
            line, used = [], 0
        if line:
            used += gap
        line.append(b)
        used += bw
    if line:
        lines.append((" " * gap).join(line))
    return lines


def divider_with(w: int, center: str = "") -> str:
    """Divisor de w columnas con un texto centrado entre '─'."""
    if not center:
        return f"{DIM}{'─' * w}{RESET}"
    cw = vis_len(center)
    if cw >= w:
        return center
    sides = w - cw
    left = sides // 2
    right = sides - left
    return f"{DIM}{'─' * left}{RESET}{center}{DIM}{'─' * right}{RESET}"


# Colores dinámicos: resuelven el código ANSI del tema activo al imprimirse,
# así la tecla "t" puede cambiar el tema en vivo dentro del modo --live.
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


def _bar(pct: float) -> tuple[str, str]:
    """Devuelve (bloque coloreado, color) según el porcentaje de uso."""
    color = GREEN if pct < 50 else YELLOW if pct < 80 else RED
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    return bar, color


def _group(title: str, blocks: list[str], w: int, decor: bool = True) -> None:
    if decor:
        print(f"{BOLD}{CYAN}── {title} ──{RESET}")
    for line in flex_wrap(blocks, w):
        print(line)


def _section(decor: bool, title: str) -> None:
    if decor:
        print(f"{BOLD}{CYAN}── {title} ──{RESET}")


def _build_footer(
    show_help: bool, toast_until: float, clock_on: bool, theme_name: str
) -> str:
    """Fila inferior: ayuda (overlay) o reloj, con el toast de tema cuando aplica.
    El reloj se omite si clock_on es falso."""
    if show_help:
        return f"{DIM}{HELP_FOOTER}{RESET}"
    parts: list[str] = []
    if time.monotonic() < toast_until:
        parts.append(f"{CYAN}theme: {theme_name}{RESET}")
    if clock_on:
        parts.append(f"{DIM}{time.strftime('%H:%M')}{RESET}")
    return "  ".join(parts)


# ────────────────────────── vistas ──────────────────────────


def full_info(args: object, threshold_bytes: int, footer: str = "") -> None:
    tw, _ = shutil.get_terminal_size((80, 30))
    w = tw
    dec = getattr(args, "decor", True)
    n = min(max(getattr(args, "top", 5), 1), 5)
    if dec:
        print(divider_with(w, f" {CYAN}MONITOR{RESET} "))

    mi = readers.read_meminfo()
    total = mi["MemTotal"]

    if getattr(args, "ram", True):
        used = total - mi["MemAvailable"]
        free = mi["MemFree"]
        _section(dec, "RAM")
        for line in flex_wrap(
            [
                f"  Usada {fmt.fmt_short(used):>5}/{fmt.fmt_short(total):<5} {used / total * 100:.1f}%",
                f"  Libre {GREEN}{fmt.fmt_short(free)}{RESET}",
            ],
            w,
        ):
            print(line)
        print(
            f"  {CYAN}Disponible{RESET} {GREEN}{fmt.fmt_short(mi['MemAvailable'])}{RESET}"
        )

    if getattr(args, "swap", False):
        swap_total = mi.get("SwapTotal", 0)
        if swap_total:
            swap_used = swap_total - mi.get("SwapFree", 0)
            _section(dec, "SWAP")
            for line in flex_wrap(
                [
                    f"  Usada {fmt.fmt_short(swap_used):>5}/{fmt.fmt_short(swap_total):<5} {swap_used / swap_total * 100:.1f}%",
                    f"  Libre {fmt.fmt_short(mi.get('SwapFree', 0))}",
                ],
                w,
            ):
                print(line)

    if getattr(args, "vram", False):
        vram = readers.read_vram()
        if vram:
            _section(dec, "VRAM")
            blocks: list[str] = []
            for card, vt, vu in vram:
                label = "dGPU" if vt >= 1024**3 else "iGPU"
                blocks.append(
                    f"  {card} {label} {fmt.fmt_short(vu):>5}/{fmt.fmt_short(vt):<5} {vu / vt * 100:.1f}%"
                )
            for line in flex_wrap(blocks, w):
                print(line)

    if getattr(args, "cpu", True):
        _section(dec, "CPU")
        with open("/proc/loadavg") as f:
            load = f.read().strip()
        before = readers.read_cpu_lines()
        time.sleep(0.2)
        after = readers.read_cpu_lines()
        pct_by_core = readers.cpu_pct_from_lines(before, after)
        total_pct = pct_by_core.get("cpu", 0.0)
        print(
            f"  Load {load.split()[0]} · {os.cpu_count() or 0}c · {DIM}Total {total_pct:.1f}%{RESET}"
        )
        core_blocks: list[str] = []
        for cid, use_pct in pct_by_core.items():
            if cid == "cpu":
                continue
            bar, color = _bar(use_pct)
            core_blocks.append(f"  {color}{bar}{RESET} {cid} {fmt.fmt_pct(use_pct)}")
        for line in flex_wrap(core_blocks, w):
            print(line)

    if getattr(args, "disk", False):
        usage = shutil.disk_usage("/")
        used_pct = usage.used / usage.total * 100 if usage.total else 0
        _section(dec, "DISCO")
        for line in flex_wrap(
            [
                f"  / {fmt.fmt_short(usage.used):>5}/{fmt.fmt_short(usage.total):<5} {used_pct:.1f}%",
                f"  Libre {GREEN}{fmt.fmt_short(usage.free)}{RESET}",
            ],
            w,
        ):
            print(line)
        before = readers.disk_stats()
        time.sleep(0.2)
        after = readers.disk_stats()
        io_blocks: list[str] = []
        for name, (r_after, w_after) in after.items():
            r_before, w_before = before.get(name, (r_after, w_after))
            read_rate = (r_after - r_before) / 0.2
            write_rate = (w_after - w_before) / 0.2
            if read_rate or write_rate:
                io_blocks.append(
                    f"  {name}: {CYAN}R {fmt.fmt_rate(read_rate)}{RESET} {YELLOW}W {fmt.fmt_rate(write_rate)}{RESET}"
                )
        for line in flex_wrap(io_blocks, w):
            print(line)

    if getattr(args, "network", False):
        _section(dec, "RED")
        before = readers.net_stats()
        time.sleep(0.2)
        after = readers.net_stats()
        if after:
            net_blocks: list[str] = []
            for iface, (rx_after, tx_after) in after.items():
                rx_before, tx_before = before.get(iface, (rx_after, tx_after))
                rx_rate = (rx_after - rx_before) / 0.2
                tx_rate = (tx_after - tx_before) / 0.2
                net_blocks.append(
                    f"  {iface}: {GREEN}↓ {fmt.fmt_rate(rx_rate)}{RESET} {YELLOW}↑ {fmt.fmt_rate(tx_rate)}{RESET}"
                )
            for line in flex_wrap(net_blocks, w):
                print(line)
        else:
            print(f"  {DIM}Sin interfaces activas{RESET}")

    procs = readers.read_procs()
    if getattr(args, "top_procs", True):
        pblocks = []
        for rss, pid, name in procs[:n]:
            num = f"{RED if rss >= threshold_bytes else DIM}{fmt.fmt_short(rss):>6}{RESET}"
            pblocks.append(f"  {num} {DIM}{pid:<6} {name}{RESET}")
        _group("TOP RAM", pblocks, w, dec)

    if getattr(args, "top_cpu", True):
        candidates = procs[:40]
        t1 = {pid: readers.cpu_time(pid) for _, pid, _ in candidates}
        time.sleep(0.1)
        cpu_procs: list[tuple[float, str, str]] = []
        for rss, pid, name in candidates:
            before_t, after_t = t1.get(pid), readers.cpu_time(pid)
            if before_t is None or after_t is None:
                continue
            cpu_procs.append(((after_t - before_t) / 0.1, pid, name))
        cpu_procs.sort(reverse=True)
        cblocks = [
            f"  {DIM}{fmt.fmt_pct(pct):>7} {name}{RESET}"
            for pct, _, name in cpu_procs[:n]
        ]
        _group("TOP CPU", cblocks, w, dec)

    if dec:
        print(divider_with(w, footer))
    elif footer:
        print(footer)


def short_info(args: object, threshold_bytes: int, footer: str = "") -> None:
    tw, _ = shutil.get_terminal_size((40, 20))
    w = min(tw, 40)
    dec = getattr(args, "decor", True)
    n = min(max(getattr(args, "top", 5), 1), 5)
    sep = divider_with(w)
    head = divider_with(w, f" {CYAN}MONITOR{RESET} ")

    blocks: list[str] = []
    mi = readers.read_meminfo()

    total = mi["MemTotal"]
    if getattr(args, "ram", True):
        used = total - mi["MemAvailable"]
        blocks.append(
            f"  {CYAN}RAM{RESET} {fmt.fmt_short(used):>6}/{fmt.fmt_short(total):<6} {used / total * 100:.1f}%"
        )

    if getattr(args, "cpu", True):
        with open("/proc/loadavg") as f:
            load = f.read().strip().split()[0]
        blocks.append(f"  {CYAN}CPU{RESET} {load:>5}  {os.cpu_count() or 0}c")

    if getattr(args, "swap", False):
        swap_total = mi.get("SwapTotal", 0)
        if swap_total:
            swap_used = swap_total - mi.get("SwapFree", 0)
            blocks.append(
                f"  {YELLOW}SWP{RESET} {fmt.fmt_short(swap_used):>6}/{fmt.fmt_short(swap_total):<6} {swap_used / swap_total * 100:.1f}%"
            )

    if getattr(args, "vram", False):
        for card, vt, vu in readers.read_vram():
            blocks.append(
                f"  {DIM}GPU{RESET} {fmt.fmt_short(vu):>6}/{fmt.fmt_short(vt):<6} {vu / vt * 100:.1f}%"
            )

    if getattr(args, "disk", False):
        usage = shutil.disk_usage("/")
        blocks.append(
            f"  {CYAN}DSK{RESET} {fmt.fmt_short(usage.used):>6}/{fmt.fmt_short(usage.total):<6} {usage.used / usage.total * 100:.1f}%"
        )

    if getattr(args, "network", False):
        before = readers.net_stats()
        time.sleep(0.2)
        after = readers.net_stats()
        rx = sum(a[0] - before.get(i, a)[0] for i, a in after.items()) / 0.2
        tx = sum(a[1] - before.get(i, a)[1] for i, a in after.items()) / 0.2
        blocks.append(
            f"  {CYAN}NET{RESET} ↓{fmt.fmt_short(rx)}/s ↑{fmt.fmt_short(tx)}/s"
        )

    if dec:
        print(head)
    for line in flex_wrap(blocks, w):
        print(line)

    procs = readers.read_procs(n * 2)
    if dec:
        print(sep)
    pblocks: list[str] = []
    for rss, _, name in procs[:n]:
        txt = f"  {fmt.fmt_short(rss):>6}  {name}"[: w - 2]
        color = RED if rss >= threshold_bytes else DIM
        pblocks.append(f" {color}{txt}{RESET}")
    for line in flex_wrap(pblocks, w):
        print(line)

    if dec:
        print(divider_with(w, footer))
    elif footer:
        print(footer)


TOGGLE_KEYS = {
    "1": ("ram", "RAM"),
    "2": ("cpu", "CPU"),
    "3": ("swap", "Swap"),
    "4": ("vram", "VRAM"),
    "5": ("disk", "Disco"),
    "6": ("network", "Red"),
    "7": ("top_procs", "Top RAM"),
    "8": ("top_cpu", "Top CPU"),
    "9": ("clock", "Reloj"),
    "0": ("decor", "Header/divisores"),
}

TOAST_SECONDS = 3.0

HELP_FOOTER = (
    "[1]RAM [2]CPU [3]SWP [4]VRAM [5]DSK [6]NET "
    "[7]TopRAM [8]TopCPU [9]Reloj [0]Decor  |  "
    "[m]modo [c]config [t]tema [u]update [?]ayuda [q]salir"
)


def _config_screen(args: object, w: int) -> None:
    """Pantalla de configuración (tecla c): lista de campos numerados."""
    print(f"{BOLD}{CYAN}── CONFIG ──{RESET}")
    print(
        f"  {CYAN}1{RESET}) Umbral RAM (GB)      [{GREEN}{args.threshold}{RESET}]  "
        f"procesos > umbral resaltados"
    )
    print(f"  {CYAN}2{RESET}) Top procesos         [{GREEN}{args.top}{RESET}]  (1-5)")
    print(f"  {CYAN}3{RESET}) Intervalo refresco   [{GREEN}{args.interval}{RESET}s]")
    print()
    print(f"  {DIM}[1-3] editar · [0/esc/q] volver{RESET}")


def _config_edit_field(args: object, key: str) -> None:
    """Edita el campo correspondiente a la tecla 1/2/3 dentro del navegador de config."""
    try:
        if key == "1":
            raw = input(f"{CYAN}umbral RAM GB [{GREEN}{args.threshold}{RESET}]: ")
            if raw.strip():
                args.threshold = max(float(raw), 0.1)
        elif key == "2":
            raw = input(f"{CYAN}top procesos [{GREEN}{args.top}{RESET}] (1-5): ")
            if raw.strip():
                args.top = min(max(int(float(raw)), 1), 5)
        else:
            raw = input(f"{CYAN}intervalo s [{GREEN}{args.interval}{RESET}]: ")
            if raw.strip():
                args.interval = max(float(raw), 0.2)
    except (EOFError, KeyboardInterrupt):
        pass
    except ValueError:
        print(
            f"  {DIM}(valor inválido: número con punto decimal, vacío mantiene){RESET}"
        )


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
        print("El modo en vivo (--live) requiere una terminal.", file=sys.stderr)
        sys.exit(1)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ECHO | termios.ICANON)
    new[6][termios.VMIN] = 0
    new[6][termios.VTIME] = 1

    show_help = False
    config_mode = False  # tecla c: pantalla de configuración
    theme_feedback_until = 0.0  # timestamp (monotonic) hasta el que se muestra el toast

    def render() -> None:
        nonlocal theme_feedback_until
        buf = io.StringIO()
        old_out = sys.stdout
        sys.stdout = buf
        try:
            tw, th = shutil.get_terminal_size()
            pad = max(0, (th - 12) // 2)
            if config_mode:
                _config_screen(args, tw)
            else:
                footer = _build_footer(
                    show_help,
                    theme_feedback_until,
                    getattr(args, "clock", True),
                    args.theme,
                )
                if args.short:
                    short_info(args, threshold_bytes, footer)
                else:
                    full_info(args, threshold_bytes, footer)
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
                if config_mode:
                    if k in ("0", "q", "\x1b"):
                        config_mode = False
                        render()
                    elif k in ("1", "2", "3"):
                        termios.tcsetattr(fd, termios.TCSADRAIN, old)
                        _config_edit_field(args, k)
                        termios.tcsetattr(fd, termios.TCSADRAIN, new)
                        threshold_bytes = int(args.threshold * 1024**3)
                        if not args.no_config:
                            from monitor.config import config_from_args, save_config

                            save_config(config_from_args(args))
                        render()
                    continue
                if k in ("q", "\x1b"):
                    return
                if k in ("?", "h"):
                    show_help = not show_help
                    render()
                    continue
                if k == "m":
                    args.short = not args.short
                    render()
                    continue
                if k == "c":
                    config_mode = True
                    render()
                    continue
                if k == "t":
                    theme.cycle_theme()
                    args.theme = theme.ACTIVE
                    if not args.no_config:
                        from monitor.config import config_from_args, save_config

                        save_config(config_from_args(args))
                    theme_feedback_until = (
                        time.monotonic() + TOAST_SECONDS
                    )  # toast con autolimpieza
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
