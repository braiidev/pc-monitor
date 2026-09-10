# pc-monitor

Monitor de sistema en consola: RAM, SWAP, VRAM, CPU, disco, red y top procesos. En Python puro (solo stdlib), instalable y actualizable en una línea.

## Instalar

```bash
curl -fsSL https://raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh | bash
```

Instala sin sudo: código en `~/.local/share/pc-monitor/`, comando `monitor` en `~/.local/bin/monitor` (symlink al venv). La configuración queda en `~/.config/monitor/` y no se toca.

### Dependencias por sistema

| Sistema | Comando |
|---|---|
| Debian/Ubuntu | `sudo apt install git python3 python3-venv` |
| Alpine | `apk add git python3 py3-pip py3-virtualenv` |

En Alpine no está `bash` (usa `sh`); el mismo script funciona con cualquiera de los dos:

```sh
curl -fsSL https://raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh | sh
```

### Nota para desarrollo

`install.sh` clona el repo remoto, así que para instalar tus propios cambios primero hay que pushear:

```bash
git push origin main
```

## Usar

```bash
monitor            # estado completo (one-shot; -l para en vivo)
monitor -l         # modo en vivo con refresco periódico
monitor --once     # imprime una vez y sale
monitor -s         # vista compacta
monitor --full     # vista completa
monitor 2          # umbral de 2GB para marcar procesos excesivos
monitor --disk --network   # incluir disco y red
```

| Argumento | Acción |
|---|---|
| `threshold` | Umbral en GB de RAM para marcar procesos excesivos |
| `-l, --live / --once` | Modo en vivo (refresco) / one-shot (una vez y sale) |
| `-s, --short / --full` | Vista compacta (bloques con flex-wrap) / completa |
| `-n, --top N` | Procesos listados en los tops (1-5) |
| `--interval S` | Segundos entre refrescos en `--live` |
| `--theme NOMBRE` | Tema de color: `clasico`, `mono`, `calido`, `alto_contraste`, `flatline`, `custom` |
| `--config` | Abre `$EDITOR` en la config (general, secciones y paleta `custom`) y sale |
| `--ram / --cpu / --swap / --vram / --disk / --network` | Toggle de secciones (con `--no-*`) |
| `--top-procs / --top-cpu` | Toggle de top procesos (RAM / sample por CPU) |
| `--clock / --decor` | Reloj en el divisor / header y divisores |
| `--no-config` | Ignorar y no tocar la config |

### Teclas en `--live`

Las teclas `0`–`9` muestran/ocultan cada bloque en vivo; las letras son acciones.

| Tecla | Acción |
|---|---|
| `1`–`8` | Toggle RAM / CPU / Swap / VRAM / Disco / Red / Top RAM / Top CPU |
| `9` / `0` | Toggle reloj en el divisor / header y divisores (ornamento) |
| `m` | Cambiar entre vista completa y compacta |
| `c` | Pantalla de configuración: `1` umbral RAM · `2` top procesos · `3` intervalo; `0`/Esc volver |
| `t` | Cambiar tema de color (muestra el nombre y se guarda en la config) |
| `u` | Actualizar el paquete y re-ejecutar |
| `?` | Ayuda (atajos en el divisor inferior) |
| `q` | Salir |

### Vistas

- **Completa** (`monitor`): secciones agrupadas `── TÍTULO ──` con 1–2 líneas de datos.
- **Compacta** (`monitor -s`): cada sección es un bloque de ancho variable; los bloques se acomodan en filas según el ancho de la terminal (flex-wrap) y "cae" a la línea siguiente cuando no entra.

En ambas, el divisor inferior muestra el reloj (o el toast temporal al cambiar tema/elemento).

## Configuración

Primer arranque genera `~/.config/monitor/config.toml`:

```toml
[general]
loop = false
short = false
threshold = 1.0
top = 5
interval = 2.0
theme = "clasico"

[sections]
ram = true
cpu = true
swap = true
vram = true
disk = false
network = false
top_procs = true
top_cpu = true
clock = true
decor = true

# Tema custom: paleta del tema `custom` (editable con `monitor --config`)
[custom]
red = "91"
yellow = "93"
cyan = "96"
green = "92"
```

El tema `custom` parte de la paleta `clasico`; sus valores se editan con `monitor --config` (abre `$EDITOR`). Los códigos son ANSI: vacío = sin color, o SGR válido (ej. `31`–`37`, brillantes `90`–`97`, 256 colores `38;5;N`). Valores inválidos caen a `clasico` automáticamente.

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