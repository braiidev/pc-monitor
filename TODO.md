# TODO

## Doing

## Next

### 🔧 FIX — install.sh sobrevive al upgrade a Ubuntu 26.04 (Python 3.14) — CERRADO v0.9.18

**Síntoma:** en la máquina `.38` (actualizada 24.04 → 26.04) `monitor` dejó de arrancar.

**Causa raíz — el symlink flotante, no el número de versión.** `python3 -m venv` crea:

```
.venv/bin/python -> python3
.venv/bin/python3 -> /usr/bin/python3     ← flotante
```

`/usr/bin/python3` siempre resuelve a la última versión. El venv declara `version = 3.12.3` pero
ejecuta lo que haya. Al subir a 26.04 el shebang de `.venv/bin/monitor` siguió resolviendo (3.14), así
que no hubo "comando no encontrado": corrió 3.14 sobre layout 3.12 → buscó
`lib/python3.14/site-packages`, no lo encontró, el editable quedó invisible → `ModuleNotFoundError`.

**Trampa de fondo:** el symlink moría con el venv, así que `monitor --update` tampoco servía para
reparar. La salida estaba dentro de lo roto.

**Decisión — opción B: Python del sistema versionado, detectado.** Invocar la ruta versionada y
**persistir la versión en `.pinned-python`**. Justificación: `dependencies = []`, stdlib puro. uv
agregaría una dependencia rompible sin comprar nada (0 MB, sin red para el intérprete).

- [x] v0.9.18a: `requires-python` de `>=3.9` a `>=3.10,<3.15`
- [x] v0.9.18b: install.sh resuelve el `/usr/bin/python3.X` versionado más nuevo del rango y lo persiste en `.pinned-python`
- [x] v0.9.18c: el venv se crea con la ruta versionada, nunca con `python3`; `venv_ok()` valida venv + pin + import
- [x] v0.9.18d: `venv_flota()` — detecta el enlace colgando de `/usr/bin/python3`
- [x] v0.9.18e: `~/.local/bin/monitor` es un **wrapper**, no un symlink (con health-check y auto-reparación)
- [x] v0.9.18f: `update.py` — `sync_pinned_python()`, `venv_is_floating()`, `run_installer()`, `.created-at`
- [x] v0.9.18g: smoke test (`monitor --version` con salida ≠ 0 si falla) + append idempotente de `~/.local/bin` al PATH
- [x] v0.9.18h: `tests/e2e_install.sh` con el escenario real de rompimiento + 20 tests de update.py

**La trampa propia del repo, confirmada empíricamente:** `install.sh:48` era
`if [ -e "$BIN" ] && [ ! -L "$BIN" ]; then mv "$BIN" "$BIN.bak"`. Al pasar a wrapper eso respaldaba
**nuestro propio wrapper en cada reinstalación**. El criterio ahora pasa a detectar el marcador
dentro del archivo, no "es un archivo regular" — y un symlink viejo que apunta a `$VENV` se **borra**,
porque `cat > $BIN` escribe atravesando symlinks.

**Dos decisiones de diseño que vienen de Clock y acá no se pueden copiar:**
- El wrapper **no solo avisa, repara**: si el venv no responde, corre el `install.sh` del repo y se
  relanza. Funciona porque es bash y no necesita el venv. Auto-limitado a un intento.
- Se relanza con `exec bash "$0" "${ARGS[@]}"` (no `exec "$VENV/bin/python"`): install.sh reescribe el
  wrapper mientras corre y bash lee los scripts por partes. `ARGS=("$@")` se guarda aparte porque
  dentro de `repair()` `"$@"` son los args de la función (vacíos) — sin eso se perdía `--version`.

**Nota:** se sirve desde `raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh`. El fix no
llega a otra máquina hasta que esté pusheado a `main`.

### 🔧 FIX — un cfg parcial trunca la config del usuario — CERRADO v0.9.19
**Síntoma:** en esta PC la config se "reiniciaba" al salir y volver a entrar de `monitor`.

**Lo que se pudo probar (sin adivinar):**
- `install.sh` es inocente: md5 de `~/.config/monitor/config.toml` idéntico antes y después
- El round-trip `load_config()` → `save_config()` es correcto: 313 → 782 bytes, conserva todo
- En modo live los toggles SÍ se guardan: verificado con pty real e instrumentación (`save_config` recibe `disk=False` y el archivo queda `disk = false`)
- Los 519 bytes observados son **exactamente** `_write_toml_lite({"general": {"theme"}, "sections": {}, "custom": {}})`: un dict **sin el merge de defaults**, reproducido byte a byte
- Ningún call site del código actual produce eso. Quedó sin poder probar quién lo escribió

**El bug real:** `_write_toml_lite` saltea toda clave ausente del dict, así que cualquier cfg parcial que llegara a `save_config` vaciaba las secciones y se llevaba lo que el usuario tenía. Un dict incompleto se convertía en pérdida de datos.

- [x] `_fill_missing()`: `save_config()` completa con `DEFAULT_CONFIG` lo que falta, sin pisar lo presente. Las tres secciones se escriben siempre completas
- [x] 3 tests de regresión: un cfg parcial no trunca, respeta lo presente, no muta la entrada

**Restos del "monolito" en esta PC** (la diferencia con otras máquinas): `~/.local/bin/monitor.bak` (21 KB, ago 25) y `~/.local/bin/__pycache__/monitorcpython-312.pyc` (jul 3, sin código de config). El `.bak` escribe en `~/.config/monitor.toml` (legacy), no en `config.toml`. A borrar con aprobación del usuario.

### Pendiente
- [ ] v0.9.21: `test_footer_oculto_si_no_cabe_o_config_off` de Clock (preexistente desde v0.55)
- [ ] v0.9.22: borrar `~/.local/bin/monitor.bak` y el `__pycache__` viejo (esperando OK)

### 🔧 FIX — mypy limpio, strict incluido — CERRADO v0.9.20
**Estado anterior:** 59 errores sin config de mypy. Todos eran higiene de tipos, ningún bug de runtime.

Seis causas distintas, seis arreglos:

- [x] **35 `attr-defined`** — 8 funciones con `args: object` en vez de `argparse.Namespace`: `config_from_args`, `full_info`, `short_info`, `_config_screen`, `_config_edit_field`, `loop_mode`
- [x] **6 errores de reuso de variable** — `before`/`after` se usaban primero para `list[str]` (CPU) y después para `dict` (disco, red), así que mypy los fijó al primer tipo. Separados en `dsk_before/after` y `net_before/after`
- [x] **3 errores de reuso de variable en main.py** — `p` era `str` en el loop de `targets` y `Path` en el de configs. Segundo loop renombrado a `cfg_path`
- [x] **3 `_ThemeColor.role`** — `str` no tiene `__dict__`, así que mypy no veía el atributo asignado en `__new__`. Declaración a nivel de clase
- [x] **5 errores de `DEFAULT_CONFIG`** — al no anotarse se infería `dict[str, object]` (mezcla bool/float/int/str) y contaminaba `dict(v)`, `{**defaults}` y `_write_toml_lite`. Anotada como `dict[str, dict[str, object]]`
- [x] **`_restart_process(old: object)`** y `run_centered(fn, ...)` sin anotación: `list[Any]` y `Callable[..., None]`

- [x] `pyproject.toml` ahora tiene `[tool.mypy] strict = true` + `files`, así que `mypy` a secas ya aplica strict. También `[tool.black]` con `target-version = py310` (el default de black asumía 3.14 y no podía parsear el código)
- [x] Black formateó 1 archivo; 121 tests y E2E 43/43 sin cambios de comportamiento

**Verificación:** `mypy` (strict, sin flags) → `Success: no issues found in 9 source files`.

## Done
- [x] v0.9.20 chore: mypy strict limpio (59 → 0) + config en pyproject
- [x] v0.9.19 fix: un cfg parcial ya no puede truncar la config del usuario
- [x] v0.9.18 fix: install.sh sobrevive al upgrade del SO (pin versionado + wrapper con auto-reparación)
- [x] v0.9.16 feat: contenedor siempre centrado + alineación de texto left/center/right
- [x] v0.9.15 feat: config de alineación left/right (--align, tecla a en live)
- [x] v0.9.14 feat: bloque centrado con texto alineado a la derecha (right_block)
- [x] v0.9.13 feat: centrado horizontal (one-shot + live) + auditoría (disk NVMe/eMMC, uninstall realpath, cleanups)
- [x] v0.9.12 fix: top config ignorado (vistas fijas en 3) + clamp top 1-5
- [x] v0.9.11 feat: top RAM/CPU en texto dim (full + short), rojo por umbral conservado
- [x] v0.9.10 feat: flag --config (reemplaza --theme-custom) + default inicial one-shot full (loop/short = false)
- [x] v0.9.8 feat: toggles 9/0 efectivos (reloj/decor en vistas) + config por pantalla (tecla c)
- [x] v0.9.9 refactor: normalización flags CLI (--live/--once/--full, --top-procs dasheado) + --help con opciones de monitoreo
- [x] v0.9.1 fix: loop mode roto (views L384) + TypeError float (L238) + test footer desync
- [x] v0.9.2 feat: vis_len + flex_wrap (wrap por ancho de terminal) + test_views
- [x] v0.9.3 feat: short con bloques flex-wrap + reloj en divisor + toast en fila del reloj
- [x] v0.9.4 feat: full como grupos [título + 2 líneas] + barras CPU por toggle + reloj
- [x] v0.9.5 feat: toggles 0-9 + teclas m/t/u/?/c + HELP_FOOTER nuevo + persistencia
- [x] v0.9.6 feat: config con 10 secciones [sections] + tecla c (threshold/top/interval)
- [x] v0.9.7 docs: README con atajos y bloques