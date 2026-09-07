"""Entry point de pc-monitor: CLI (update/uninstall/version) + monitor en consola."""

from __future__ import annotations

import argparse
import os
import shutil
import sys

from monitor import __version__, theme
from monitor.config import CONFIG_PATH, DEFAULT_CONFIG, LEGACY_CONFIG_PATH, load_config, save_config
from monitor.update import check_update, do_update, repo_root
from monitor import views

BIN_DIR = os.path.join(os.path.expanduser("~"), ".local", "bin")
BIN_PATH = os.path.join(BIN_DIR, "monitor")
INSTALL_DIR_EXPECTED = os.path.join(os.path.expanduser("~"), ".local", "share", "pc-monitor")

USAGE = """uso: monitor [--update | --check-update | --uninstall | --version] [opciones de monitoreo]

  (sin argumentos)   imprime el estado del sistema (o entra en --loop según config)
  --update           actualiza el paquete (git pull) y sale
  --check-update     verifica si hay versión nueva
  --uninstall        desinstala el paquete (y, si confirmás, la config)
  --version          imprime la versión instalada

Opciones de monitoreo: monitor [--help]"""


# ────────────────────────── self-management (CLI) ──────────────────────────

def _cli_update() -> int:
    res = do_update(repo_root())
    print(res.message)
    return 0 if res.ok else 1


def _cli_check_update() -> int:
    info = check_update(repo_root())
    if not info.ok:
        print(f"⚠ No se pudo verificar: {info.error}", file=sys.stderr)
        return 1
    if info.behind > 0:
        print(f"→ Hay una actualización disponible ({info.available}). Ejecutá: monitor --update")
    else:
        print(f"✓ Estás al día ({info.current})")
    return 0


def _confirm(prompt: str) -> bool:
    try:
        r = input(f"{prompt} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return r in ("y", "yes")


def _cli_uninstall() -> int:
    source = repo_root()
    if not source.startswith(INSTALL_DIR_EXPECTED):
        print(
            "Error: el código no vive en una instalación vía install.sh; no se borra.",
            file=sys.stderr,
        )
        print(f"  (repo detectado: {source})", file=sys.stderr)
        return 1

    print("▶ Desinstalando pc-monitor...")
    targets = [BIN_PATH, source]
    for p in targets:
        print(f"  ↳ {p}")
    if not _confirm("¿Eliminar la instalación? "):
        print("Cancelado.")
        return 1

    if os.path.islink(BIN_PATH) or os.path.isfile(BIN_PATH):
        try:
            os.unlink(BIN_PATH)
        except OSError:
            pass
    shutil.rmtree(source, ignore_errors=True)

    paths = [CONFIG_PATH, LEGACY_CONFIG_PATH]
    paths = [p for p in paths if p.exists()]
    if paths:
        for p in paths:
            print(f"  ↳ config en {p}")
        if _confirm("¿Borrar también la config? "):
            for p in paths:
                try:
                    p.unlink()
                except OSError:
                    pass
        else:
            print("  · config conservada en", ", ".join(str(p) for p in paths))

    print("✓ pc-monitor desinstalado")
    return 0


# ────────────────────────── monitoreo ──────────────────────────

def parse_args(cfg: dict[str, dict[str, object]]) -> argparse.Namespace:
    g, s = cfg["general"], cfg["sections"]
    p = argparse.ArgumentParser(
        prog="monitor",
        description="Monitor de sistema en consola (RAM, SWAP, VRAM, CPU, disco, red, procesos). "
        f"Config: {CONFIG_PATH}",
    )
    p.add_argument(
        "threshold",
        nargs="?",
        type=float,
        default=g["threshold"],
        help=f"Umbral en GB de RAM para marcar procesos como excesivos (default: {g['threshold']})",
    )
    p.add_argument("-l", "--loop", action=argparse.BooleanOptionalAction, default=g["loop"],
                    help="Modo en vivo, refresco periódico")
    p.add_argument("-s", "--short", action=argparse.BooleanOptionalAction, default=g["short"],
                    help="Vista compacta")
    p.add_argument("-n", "--top", type=int, default=g["top"], help="Cantidad de procesos a listar")
    p.add_argument("--interval", type=float, default=g["interval"], help="Segundos entre refrescos en --loop")
    theme_choices = ", ".join(theme.THEME_NAMES)
    p.add_argument("--theme", default=g["theme"],
                    help=f"Tema de color ({theme_choices})")
    p.add_argument("--disk", action=argparse.BooleanOptionalAction, default=s["disk"],
                    help="Incluir uso de disco (espacio + I/O)")
    p.add_argument("--network", action=argparse.BooleanOptionalAction, default=s["network"],
                    help="Incluir uso de red (rx/tx)")
    p.add_argument("--swap", action=argparse.BooleanOptionalAction, default=s["swap"],
                    help="Incluir sección de SWAP")
    p.add_argument("--vram", action=argparse.BooleanOptionalAction, default=s["vram"],
                    help="Incluir sección de VRAM")
    p.add_argument("--no-config", action="store_true", help=f"Ignorar/no tocar {CONFIG_PATH}")
    return p.parse_args()


def resolve_theme(argv: list[str], args: argparse.Namespace, cfg: dict[str, dict[str, object]], no_config: bool) -> str:
    """Valida el theme. Tema de config viejo/roto -> fallback silencioso a 'clasico'
    (y corrige el archivo). Solo --theme explícito inválido da error (SystemExit)."""
    if theme.is_theme(args.theme):
        return args.theme
    if "--theme" in argv:
        print(f"Tema desconocido: {args.theme!r} ({', '.join(theme.THEME_NAMES)})", file=sys.stderr)
        raise SystemExit(1)
    if not no_config:
        cfg["general"]["theme"] = "clasico"
        save_config(cfg)
    return "clasico"


def main() -> None:
    argv = sys.argv[1:]
    if "-h" in argv or "--help" in argv:
        print(USAGE)
        return
    if "--update" in argv:
        sys.exit(_cli_update())
    if "--check-update" in argv:
        sys.exit(_cli_check_update())
    if "--uninstall" in argv:
        sys.exit(_cli_uninstall())
    if "--version" in argv:
        print(f"monitor {__version__}")
        return

    no_config = "--no-config" in argv
    cfg = {k: dict(v) for k, v in DEFAULT_CONFIG.items()} if no_config else load_config()
    args = parse_args(cfg)
    if args.threshold <= 0:
        print("El umbral debe ser un número mayor a 0.", file=sys.stderr)
        sys.exit(1)
    # Si el tema viene de la config (vieja/rota) y ya no existe, hacer fallback
    # silencioso a clasico y corregir el archivo. Solo --theme explícito inválido da error.
    args.theme = resolve_theme(argv, args, cfg, no_config)
    theme.ACTIVE = args.theme
    threshold_bytes = int(args.threshold * 1024 ** 3)

    try:
        if args.loop:
            views.loop_mode(args, threshold_bytes)
        elif args.short:
            views.short_info(args, threshold_bytes)
        else:
            views.full_info(args, threshold_bytes)
    except KeyboardInterrupt:
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"Este script requiere Linux (/proc no disponible): {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()