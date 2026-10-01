#!/usr/bin/env bash
# E2E del instalador de pc-monitor.
#
# Corre el install.sh real contra un HOME falso, sobre un clone real del repo. No
# toca ~/.local ni ~/.config del usuario: todo vive bajo un tmpdir que se borra.
#
# Los casos de rotura importan tanto como los de éxito. Los tres bugs de la
# v0.9.18 (symlink que el instalador no borraba, alias flotante de python3,
# venv danglante sin salida) eran invisibles leyendo el código: solo aparecen
# invocando el comando como lo haría un usuario después de un upgrade del SO.
#
# Uso:  bash tests/e2e_install.sh [ruta/al/repo]
# Repo: ../../  (default)

set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ $# -ge 1 ] && SRC="$1"

ok=0
fail=0
chk() {
    local desc="$1" want="$2" got="$3"
    if [ "$want" = "$got" ]; then
        printf '  ✓ %s\n' "$desc"
        ok=$((ok + 1))
    else
        printf '  ✗ %s\n      esperado: %s\n      real:     %s\n' "$desc" "$want" "$got"
        fail=$((fail + 1))
    fi
}

echo "══ clock-clock ═══════════════════════════════════════════════════"
echo "pc-monitor — E2E de install.sh"
echo "  fuente: $SRC"

# ── Sandbox ──
SIM="$(mktemp -d "${TMPDIR:-/tmp}/monitor-e2e-XXXXXX")"
cleanup() { rm -rf "$SIM"; }
trap cleanup EXIT

HOMEDIR="$SIM/home"
CLONE="$HOMEDIR/.local/share/pc-monitor"
BIN="$HOMEDIR/.local/bin/monitor"
RC="$HOMEDIR/.zshrc"
mkdir -p "$HOMEDIR"

# Un zshrc vacío: si install.sh no lo crea, ensure_path() debe hacerlo.
: >"$RC"

# Clone de origen, de donde sale el install.sh que se prueba.
REPO_SRC="$SIM/repo-src"
git clone -q "$SRC" "$REPO_SRC" 2>/dev/null
if [ ! -d "$REPO_SRC/.git" ]; then
    echo "No se pudo clonar $SRC — ¿es un repo git?" >&2
    exit 1
fi

# El clone se queda con lo commiteado, así que un install.sh sin commit no se
# probaría nunca. Se superpone el working tree para poder testear antes del commit.
# Los commits de prueba se agregan después, sobre el origen ya parcheado.
cp "$SRC/install.sh" "$REPO_SRC/install.sh"
rm -rf "$REPO_SRC/src"
cp -r "$SRC/src" "$REPO_SRC/src"
rm -rf "$REPO_SRC/src"/*/__pycache__
git -C "$REPO_SRC" add -A >/dev/null 2>&1
git -C "$REPO_SRC" -c user.email=t@t -c user.name=t commit -q -m "working tree" 2>/dev/null

# Un commit de trabajo, para que el pull tenga algo real que hacer.
_commit_in_origin() {
    git -C "$REPO_SRC" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "$1"
}

export HOME="$HOMEDIR"
export PC_MONITOR_RC="$RC"
# Sin esto, install.sh sube el config de ZDOTDIR si existe en el HOME real.
unset ZDOTDIR 2>/dev/null || true

install_run() {
    local dir="${1:-$CLONE}"
    PC_MONITOR_DIR="$dir" PC_MONITOR_BIN="$BIN" PC_MONITOR_RC="$RC" \
        bash "$dir/install.sh" 2>&1
}

is_symlink() { [ -L "$1" ]; }

# ── 1. Instalación limpia ──
echo
echo "── instalación limpia ──"
git clone -q "$REPO_SRC" "$CLONE"
_commit_in_origin "cambio"
out=$(PC_MONITOR_DIR="$CLONE" PC_MONITOR_BIN="$BIN" PC_MONITOR_RC="$RC" bash "$CLONE/install.sh")
echo "$out" | sed 's/^/  /'

echo
chk "exit 0"                    "0"    "$([ $? -eq 0 ] && echo 0 || echo 1)"
chk "monitor --version responde" "sí"  "$("$BIN" --version >/dev/null 2>&1 && echo sí || echo no)"
chk "monitor importa el paquete" "sí"  "$("$CLONE/.venv/bin/python" -c 'import monitor' 2>/dev/null && echo sí || echo no)"
chk "~/.local/bin/monitor NO es symlink" "no" "$(is_symlink "$BIN" && echo sí || echo no)"
chk "wrapper es de install.sh"  "sí"   "$(grep -qF 'managed wrapper' "$BIN" 2>/dev/null && echo sí || echo no)"
chk "el venv NO cuelga del alias flotante" "no" \
    "$([ "$(readlink "$CLONE/.venv/bin/python3")" = "/usr/bin/python3" ] && echo sí || echo no)"
chk "el venv SÍ usa ruta versionada" "sí" \
    "$(grep -q '^python3\.[0-9]*$' <<<"$(readlink "$CLONE/.venv/bin/python3")" && echo sí || echo no)"
chk "existe .pinned-python"     "sí"   "$([ -f "$CLONE/.pinned-python" ] && echo sí || echo no)"
chk "el pin coincide con lo que corre el venv" "sí" \
    "$([ "$(readlink -f "$(cat "$CLONE/.pinned-python")")" = "$(readlink -f "$CLONE/.venv/bin/python")" ] && echo sí || echo no)"
chk "el pin es python3.X, no python3" "sí" \
    "$(grep -qE '/python3\.[0-9]+$' "$CLONE/.pinned-python" && echo sí || echo no)"
chk ".created-at en el venv"    "sí"   "$([ -f "$CLONE/.venv/.created-at" ] && echo sí || echo no)"
chk "~/.local/bin en el rc"     "sí"   "$(grep -qF '.local/bin' "$RC" && echo sí || echo no)"

# El pip console script del venv tiene que sobrevivir: es la trampa de v0.9.17.
echo
echo "── el wrapper no se endosó sobre el venv ──"
chk "console script de pip intacto" "sí" \
    "$(grep -q 'monitor' "$CLONE/.venv/bin/monitor" 2>/dev/null && ! grep -qF 'managed wrapper' "$CLONE/.venv/bin/monitor" 2>/dev/null && echo sí || echo no)"
chk "~/.local/bin/monitor es un archivo propio" "sí" \
    "$([ -f "$BIN" ] && ! [ -L "$BIN" ] && echo sí || echo no)"

# ── 2. Idempotencia ──
echo
echo "── segunda corrida: no toca nada ──"
before_inode="$(stat -c %i "$CLONE/.venv/bin/python" 2>/dev/null)"
out=$(install_run)
echo "$out" | sed 's/^/  /'
chk "reusa el venv"            "sí"  "$(grep -q 'venv sano' <<<"$out" && echo sí || echo no)"
chk "reusa el pin"             "sí"  "$(grep -q 'reusado' <<<"$out" && echo sí || echo no)"
chk "no recrea el venv"        "sí"  \
    "$([ "$(stat -c %i "$CLONE/.venv/bin/python" 2>/dev/null)" = "$before_inode" ] && echo sí || echo no)"
chk "no duplica la línea de PATH" "1" \
    "$(grep -cF '.local/bin' "$RC")"

# ── 3. Pull con cambios ──
echo
echo "── actualización con commits nuevos ──"
_commit_in_origin "otro cambio"
out=$(install_run)
echo "$out" | sed 's/^/  /'
chk "hace pull"                "sí"  "$(grep -q 'ya existe, actualizando' <<<"$out" && echo sí || echo no)"
chk "sigue sano"               "sí"  "$("$BIN" --version >/dev/null 2>&1 && echo sí || echo no)"

# ── 4. Venv anclado al alias flotante ──
echo
echo "── SIMULO `python3 -m venv`: el venv cuelga del alias flotante ──"
ln -sf /usr/bin/python3 "$CLONE/.venv/bin/python3"
ln -sf /usr/bin/python3 "$CLONE/.venv/bin/python"
echo "  .venv/bin/python3 -> $(readlink "$CLONE/.venv/bin/python3")"
out=$(install_run)
echo "$out" | sed 's/^/  /'
chk "detecta el venv flotante" "sí"  "$(grep -q 'alias flotante' <<<"$out" && echo sí || echo no)"
chk "lo recrea versionado"     "sí"  "$(grep -q 'venv creado con' <<<"$out" && echo sí || echo no)"
chk "ya no está flotante"      "no"  \
    "$([ "$(readlink "$CLONE/.venv/bin/python3")" = "/usr/bin/python3" ] && echo sí || echo no)"
chk "vuelve a funcionar"       "sí"  "$("$BIN" --version >/dev/null 2>&1 && echo sí || echo no)"
chk "el pin se reapuntó"       "sí"  \
    "$([ "$(readlink -f "$(cat "$CLONE/.pinned-python")")" = "$(readlink -f "$CLONE/.venv/bin/python")" ] && echo sí || echo no)"

# ── 5. Venv que no responde (upgrade de SO) ──
# El caso que antes no tenía salida: el pin desaparece y `monitor --update` no
# puede reparar, porque el comando que lo haría es el mismo venv muerto. El
# wrapper es bash, así que puede repararse solo.
echo
echo "── SIMULO upgrade de SO: la versión pineada desaparece ──"
ln -sf /usr/bin/python3.99 "$CLONE/.venv/bin/python3"
ln -sf python3.99 "$CLONE/.venv/bin/python"
printf '/usr/bin/python3.99\n' >"$CLONE/.pinned-python"
echo "  pin: /usr/bin/python3.99 (no existe)   .venv/bin/python -> python3.99"

echo
echo "── monitor se repara solo, sin que el usuario copie nada ──"
out=$("$BIN" --version 2>&1); rc=$?
echo "$out" | sed 's/^/  /'
chk "termina bien"             "0"    "$rc"
chk "anuncia que repara"       "sí"   "$(grep -q 'Reparando' <<<"$out" && echo sí || echo no)"
chk "vuelve a funcionar"       "sí"   "$(grep -q '^monitor ' <<<"$out" && echo sí || echo no)"
chk "ya no está danglante"     "sí"   "$([ -x "$CLONE/.venv/bin/python" ] && echo sí || echo no)"
chk "venv importable"          "sí"   "$("$CLONE/.venv/bin/python" -c 'import monitor' 2>/dev/null && echo sí || echo no)"
chk "no pide comando manual"   "sí"   "$(grep -q 'Reparalo a mano' <<<"$out" && echo no || echo sí)"
chk "pin realineado"           "no"   "$([ "$(cat "$CLONE/.pinned-python")" = "/usr/bin/python3.99" ] && echo sí || echo no)"
chk "sigue siendo wrapper"     "no"   "$(is_symlink "$BIN" && echo sí || echo no)"
chk "console script de pip intacto" "sí" \
    "$(grep -q 'monitor' "$CLONE/.venv/bin/monitor" 2>/dev/null && ! grep -qF 'managed wrapper' "$CLONE/.venv/bin/monitor" 2>/dev/null && echo sí || echo no)"

echo
echo "── no entra en loop si la reparación no sirve ──"
cp "$CLONE/install.sh" "$CLONE/install.sh.bak"
printf '#!/usr/bin/env bash\nexit 1\n' >"$CLONE/install.sh"
rm -f "$CLONE/.venv/bin/python"; ln -sf python3.99 "$CLONE/.venv/bin/python"
out2=$(timeout 60 "$BIN" --version 2>&1); rc2=$?
chk "termina (no cuelga)"      "sí"   "$([ $rc2 -ne 124 ] && echo sí || echo no)"
chk "no es éxito"              "sí"   "$([ $rc2 -ne 0 ] && echo sí || echo no)"
chk "ofrece el comando manual" "sí"   "$(grep -q 'Reparalo a mano' <<<"$out2" && echo sí || echo no)"
chk "avisó que la reparación falló" "sí" \
    "$(grep -q 'reparación automática falló' <<<"$out2" && echo sí || echo no)"
echo "$out2" | tail -3 | sed 's/^/  /'
mv "$CLONE/install.sh.bak" "$CLONE/install.sh"

echo
echo "── segundo monitor tras reparar: sin ruido ──"
# El paso anterior dejó el venv roto a propósito (install.sh estaba stubbeado).
# Con install.sh devuelto pero sin correr, monitor tiene que volver a reparar: es
# lo correcto, porque el venv sigue muerto. Primero se sana, y recién ahí se
# verifica que una invocación sana no vuelva a anunciar nada.
out3=$("$BIN" --version 2>&1)
chk "vuelve a reparar mientras siga roto" "sí" "$(grep -q 'Reparando' <<<"$out3" && echo sí || echo no)"
chk "y funciona"               "sí"   "$(grep -q '^monitor ' <<<"$out3" && echo sí || echo no)"
out4=$("$BIN" --version 2>&1)
chk "ya sano: no anuncia reparación" "sí" "$(grep -q 'Reparando' <<<"$out4" && echo no || echo sí)"
chk "ya sano: no pide comando manual" "sí" "$(grep -q 'Reparalo a mano' <<<"$out4" && echo no || echo sí)"

# ── 6. Datos intactos ──
echo
echo "── datos personales intactos ──"
mkdir -p "$HOMEDIR/.config/monitor"
printf 'custom = 1\n' >"$HOMEDIR/.config/monitor/config.toml"
out=$(install_run)
chk "el install no toca ~/.config/monitor" "custom = 1" "$(cat "$HOMEDIR/.config/monitor/config.toml")"

echo
echo "── resumen ──"
echo "  ok: $ok   fallos: $fail"
if [ "$fail" -eq 0 ]; then
    echo
    echo "E2E OK"
    exit 0
fi
echo
echo "E2E FALLÓ"
exit 1
