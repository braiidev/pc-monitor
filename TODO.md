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

### Pendiente
- [ ] v0.9.19: los 59 errores de mypy preexistentes en `main.py`, `config.py` y `views.py` (el proyecto no tiene config de mypy; `update.py` ya está limpio)
- [ ] v0.9.20: `test_footer_oculto_si_no_cabe_o_config_off` de Clock (preexistente desde v0.55)

## Done
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