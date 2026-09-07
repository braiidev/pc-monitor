# pc-monitor

Monitor de sistema en consola: RAM, SWAP, VRAM, CPU, disco, red y top procesos. En Python puro (solo stdlib), instalable y actualizable en una línea.

## Instalar

```bash
curl -fsSL https://raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh | bash
```

Instala sin sudo: código en `~/.local/share/pc-monitor/`, comando `monitor` en `~/.local/bin/monitor` (symlink al venv). La configuración queda en `~/.config/monitor/` y no se toca.

## Usar

```bash
monitor            # estado completo (o --loop según config)
monitor -l         # modo en vivo con refresco periódico
monitor -s         # vista compacta
monitor 2          # umbral de 2GB para marcar procesos excesivos
monitor --disk --network   # incluir disco y red
```

| Argumento | Acción |
|---|---|
| `threshold` | Umbral en GB de RAM para marcar procesos excesivos |
| `-l, --loop / --no-loop` | Modo en vivo |
| `-s, --short / --no-short` | Vista compacta |
| `-n, --top N` | Cantidad de procesos a listar |
| `--interval S` | Segundos entre refrescos en `--loop` |
| `--disk / --network / --swap / --vram` | Toggle de secciones |
| `--no-config` | Ignorar y no tocar la config |

### Teclas en `--loop`

| Tecla | Acción |
|---|---|
| `1`–`5` | Vista corta / Disco / Red / Swap / VRAM |
| `?` | Ayuda |
| `q` | Salir |

## Configuración

Primer arranque genera `~/.config/monitor/config.toml`:

```toml
[general]
loop = true
short = true
threshold = 1.0
top = 5
interval = 2.0

[sections]
disk = false
network = false
swap = true
vram = true
```

## Actualizar

```bash
monitor --check-update      # consulta si hay versión nueva
monitor --update            # actualiza (git pull; corrige historial si diverge)
```

## Desinstalar

```bash
monitor --uninstall         # pide confirmación; conserva o borra la config
```

## Desarrollo

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pytest            # tests en tests/
```