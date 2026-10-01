# TODO

## Doing

## Next

### 🔧 FIX — install.sh sobrevive al upgrade a Ubuntu 26.04 (Python 3.14)

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

**Verificado empíricamente** (3 formas de crear venv, mismo repo):

| Método | `.venv/bin/python` apunta a | ¿Sobrevive upgrade del SO? |
|---|---|---|
| `python3 -m venv` | `/usr/bin/python3` ← flotante | ❌ se rompe en silencio |
| `python3.14 -m venv` | `/usr/bin/python3.14` | ✅ |
| `uv venv --python /usr/bin/python3.14` | `/usr/bin/python3.14` | ✅ |

**Decisión para monitor — opción B: Python del sistema versionado, detectado.** Invocar la ruta
versionada y **persistir la versión en `.pinned-python`** para que `--update` sepa qué validar.
Justificación: `dependencies = []`, stdlib puro. uv agregaría una dependencia rompible sin comprar
nada (0 MB, sin red para el intérprete).

- [ ] v0.9.17: acota `requires-python` de `>=3.9` a `>=3.10,<3.15`. **Sin** `uv.lock`: sin deps no hay nada que resolver
- [ ] v0.9.18: install.sh — resolver el `/usr/bin/python3.X` versionado más nuevo del rango + **persistirlo en `.pinned-python`**
- [ ] v0.9.19: install.sh — recrear el venv con la ruta versionada (nunca con `python3`); auto-reparar si `.venv/bin/python` no responde o su versión ≠ la pineada
- [ ] v0.9.20: wrapper `~/.local/bin/monitor` en vez de symlink — valida venv + versión pineada, repara o imprime el comando exacto
- [ ] v0.9.21: `update.py` — `do_update()` valida la versión pineada y reconstruye el venv si el SO subió de minor (reusa el patrón de clock)
- [ ] v0.9.22: smoke test final (`monitor --version`) con salida ≠ 0 si falla + append idempotente de `~/.local/bin` al PATH
- [ ] v0.9.23: regenerar `~/Dev/MonitorPC/.venv` (entorno de desarrollo, separado del instalado) + test del escenario real (venv flotante → se detecta y repara) + README

**Entrega:** un solo commit (v0.9.17-v0.9.23 unificados) + `git tag v0.9.17`, con este bloque como registro.

**⚠️ Trampa propia de este repo — corregir antes que nada lo del wrapper:**
`install.sh:48` tiene `if [ -e "$BIN" ] && [ ! -L "$BIN" ]; then mv "$BIN" "$BIN.bak"`.
Al pasar a wrapper (archivo regular, no symlink) eso respaldaría **nuestro propio wrapper en cada
reinstalación**. El criterio tiene que pasar a detectar nuestro marcador dentro del archivo, no
"es un archivo regular".

**No tocar:** `--uninstall` sigue funcionando (`os.unlink` borra symlink o archivo regular, y usa
`realpath` para validar que el repo viva en `~/.local/share/pc-monitor`); la config en `~/.config/monitor`
queda intacta.

**Nota:** se sirve desde `raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh`. El fix no
llega a otra máquina hasta que esté pusheado a `main`.

## Done
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