#!/usr/bin/env bash
# install.sh — Instala/actualiza pc-monitor (monitor de sistema en consola)
# Uso: curl -fsSL https://raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh | bash
# Instala SIN sudo en ~/.local: código en ~/.local/share/pc-monitor, comando en ~/.local/bin/monitor.
# Configuración personal: vive en ~/.config/monitor y NO se toca.
#
# ── Por qué el venv se crea con la RUTA VERSIONADA del intérprete ──
# `python3 -m venv` graba .venv/bin/python3 -> /usr/bin/python3. Ese symlink flotante
# SIEMPRE resuelve a la última versión de Python instalada, así que al subir el SO el venv
# queda con layout de una versión ejecutando el intérprete de otra: el install editable se
# vuelve invisible y monitor muere con ModuleNotFoundError. Invocando /usr/bin/python3.14 -m
# venv el symlink queda en la ruta versionada y sobrevive al upgrade. La versión elegida se
# persiste en .pinned-python para que las próximas ejecuciones no se desvíen.
#
# Overrides (tests): PC_MONITOR_DIR, PC_MONITOR_BIN, PC_MONITOR_RC

set -euo pipefail

REPO_URL="https://github.com/braiidev/pc-monitor.git"
RAW_INSTALL="https://raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh"
TARGET="${PC_MONITOR_DIR:-$HOME/.local/share/pc-monitor}"
BIN="${PC_MONITOR_BIN:-$HOME/.local/bin/monitor}"
VENV="$TARGET/.venv"
PINNED="$TARGET/.pinned-python"
WRAPPER_MARKER="# pc-monitor: managed wrapper (install.sh) — no editar a mano"

# Rango de interpreters aceptados. Subir MAX_MINOR es una decisión explícita del
# proyecto: hasta entonces no se apunta a una versión mayor sin verificar.
MIN_MINOR=10
MAX_MINOR=15

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

# major.minor de un intérprete; vacío si no responde.
py_minor() {
    [ -x "$1" ] || return 1
    "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null
}

in_range() {
    local maj="${1%%.*}" min="${1##*.}"
    [ "$maj" = "3" ] || return 1
    [ "$min" -ge "$MIN_MINOR" ] 2>/dev/null && [ "$min" -lt "$MAX_MINOR" ] 2>/dev/null
}

# Devuelve la ruta del mejor intérprete VERSIONADO disponible en el rango.
# Ignora a propósito /usr/bin/python3 (el flotante): solo python3.X.
resolve_python() {
    local cand best="" best_min=-1 minor real v
    for cand in /usr/bin/python3.* /usr/local/bin/python3.*; do
        [ -x "$cand" ] || continue
        case "${cand##*/}" in
            python3.*) ;;
            *) continue ;;
        esac
        v="$(py_minor "$cand")" || continue
        in_range "$v" || continue
        minor="${cand##*.}"
        case "$minor" in
            *[!0-9]*) continue ;;
        esac
        if [ "$minor" -gt "$best_min" ]; then
            best_min="$minor"
            real="$(readlink -f "$cand" 2>/dev/null || printf '%s' "$cand")"
            best="$real"
        fi
    done
    [ -n "$best" ] || return 1
    printf '%s\n' "$best"
}

# Intérprete a usar: el pineado si sigue vivo, si no el mejor disponible.
pick_python() {
    local pinned_py="" pinned_real
    if [ -f "$PINNED" ]; then
        pinned_py="$(cat "$PINNED")"
        pinned_real="$(readlink -f "$pinned_py" 2>/dev/null || printf '%s' "$pinned_py")"
        if [ -x "$pinned_real" ] && in_range "$(py_minor "$pinned_real" || true)"; then
            printf '%s\n' "$pinned_real"
            return 0
        fi
    fi
    resolve_python
}

# ¿El venv cuelga del alias flotante /usr/bin/python3?
#
# Comparar rutas RESUELTAS no alcanza: un venv flotante (python → python3 →
# /usr/bin/python3 → python3.12) resuelve exactamente a la misma ruta que uno
# sano, así que un health-check por destino lo daría por bueno. El destino no
# delata la estructura; hay que recorrer el enlace.
#   sano:     .venv/bin/python3 -> python3.12
#   flotante: .venv/bin/python3 -> /usr/bin/python3
# Un venv con --copies no tiene symlink: readlink falla y se considera estable.
venv_flota() {
    local target abs
    target="$(readlink "$VENV/bin/python3" 2>/dev/null)" || return 1
    [ -n "$target" ] || return 1
    case "$target" in
        /*) abs="$target" ;;
        *) abs="$VENV/bin/$target" ;;
    esac
    # Si el destino final no es symlink, no puede cambiar de versión: estable.
    [ -L "$abs" ] || return 1
    case "${abs##*/}" in
        python3) return 0 ;;
    esac
    return 1
}

# ¿El venv responde, corre el intérprete pineado, y el paquete se importa?
venv_ok() {
    [ -x "$VENV/bin/python" ] || return 1
    venv_flota && return 1
    "$VENV/bin/python" -c '' >/dev/null 2>&1 || return 1
    [ -f "$PINNED" ] || return 1
    local want have
    want="$(readlink -f "$(cat "$PINNED")" 2>/dev/null || true)"
    have="$(readlink -f "$VENV/bin/python" 2>/dev/null || true)"
    [ -n "$want" ] || return 1
    [ "$want" = "$have" ] || return 1
    "$VENV/bin/python" -c 'import monitor' >/dev/null 2>&1
}

create_venv() {
    # $1 = ruta versionada del intérprete. Nunca `python3`.
    "$1" -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -e "$TARGET"
    # Marca de recreación con nanosegundos. update.py la compara antes y después
    # de reejecutar este script para poder avisar "reiniciá monitor": si el venv
    # se reemplazó, el proceso que corre quedó apuntando a un árbol que ya no
    # existe. (Comparar el inode del symlink no sirve: al borrarlo y recrearlo el
    # filesystem reutiliza el número y el rebuild pasa inadvertido.)
    date +%s%N >"$VENV/.created-at"
}

# ~/.local/bin/monitor deja de ser un symlink al venv y pasa a ser un wrapper con
# health-check Y auto-reparación.
#
# Por qué puede repararse solo: este script es bash, no Python. No necesita el venv
# para correr, así que puede ejecutar install.sh (que solo usa git y un
# /usr/bin/python3.X del sistema) aunque el venv esté muerto. Ese es exactamente el
# caso del upgrade de SO que lo dejaba sin salida: cuando el venv cuelga de una
# versión que el SO borró, `monitor --update` tampoco puede correr, porque el comando
# que lo haría está muerto.
write_wrapper() {
    mkdir -p "$(dirname "$BIN")"
    cat >"$BIN" <<EOF
#!/usr/bin/env bash
$WRAPPER_MARKER
set -uo pipefail

VENV="$VENV"
PINNED="$PINNED"
DEST="$TARGET"
REPAIR="curl -fsSL $RAW_INSTALL | bash"

# Los argumentos del comando se guardan aparte porque dentro de repair() "\$@"
# son los de la función (vacíos), no los del wrapper: sin esto el relanzamiento
# perdería --version y entraría directo al monitor.
ARGS=("\$@")
[ "\${#ARGS[@]}" -gt 0 ] || ARGS=()

# Intenta reconstruir el entorno con el install.sh que ya está en el repo. Es bash
# puro, así que funciona aunque el venv no exista. Auto-limitado a un intento por
# invocación para no quedar en loop si install.sh no lo logra.
repair() {
    local n="\${PC_MONITOR_REPAIR_ATTEMPT:-0}"
    if [ "\$n" -ge 1 ]; then
        return 1
    fi
    if [ ! -f "\$DEST/install.sh" ] || ! command -v git >/dev/null 2>&1; then
        return 1
    fi
    echo "monitor: el entorno virtual no sirve. Reparando..." >&2
    if ! PC_MONITOR_DIR="\$DEST" PC_MONITOR_REPAIR_ATTEMPT=1 bash "\$DEST/install.sh" >&2; then
        echo "monitor: la reparación automática falló." >&2
        return 1
    fi
    # install.sh acaba de REESCRIBIR este mismo archivo. Bash lee los scripts por
    # partes y no vuelve atrás, así que seguir ejecutando acá leería basura del
    # archivo viejo. Hay que releer el wrapper nuevo desde \$0.
    #
    # PC_MONITOR_REPAIR_ATTEMPT=1 evita el loop: si el wrapper recién escrito sigue
    # sin encontrar venv, esta segunda pasada no repara y cae al mensaje final.
    PC_MONITOR_REPAIR_ATTEMPT=1 exec bash "\$0" "\${ARGS[@]}"
}

# El venv no responde (intérprete borrado por un upgrade del SO, o venv roto).
if [ ! -x "\$VENV/bin/python" ] || ! "\$VENV/bin/python" -c '' >/dev/null 2>&1; then
    echo "monitor: el entorno virtual está roto — \$VENV/bin/python no responde." >&2
    if [ -f "\$PINNED" ]; then
        echo "  intérprete pineado: \$(cat "\$PINNED") (ya no existe o no es ejecutable)" >&2
    fi
    if repair; then
        exit 1
    fi
    echo "  Reparalo a mano con:  \$REPAIR" >&2
    exit 1
fi

# Cubre el caso del upgrade del SO: layout del venv y versión del intérprete
# desalineados dejan el install editable invisible (ModuleNotFoundError).
if ! "\$VENV/bin/python" -c 'import monitor' >/dev/null 2>&1; then
    echo "monitor: el paquete monitor no se importa con \$VENV/bin/python." >&2
    echo "  Suele ser un venv viejo (\$(\$VENV/bin/python -V 2>&1)) re-hecho contra otra versión." >&2
    if repair; then
        exit 1
    fi
    echo "  Reparalo a mano con:  \$REPAIR" >&2
    exit 1
fi

# Aviso (no error): el venv funciona, pero el pin quedó desalineado. install.sh lo
# corrige en la próxima corrida, así que no vale la pena tocar nada.
if [ -f "\$PINNED" ]; then
    pinned_real="\$(readlink -f "\$(cat "\$PINNED")" 2>/dev/null || true)"
    have_real="\$(readlink -f "\$VENV/bin/python" 2>/dev/null || true)"
    if [ -n "\$pinned_real" ] && [ "\$pinned_real" != "\$have_real" ]; then
        echo "monitor: aviso — el venv corre \$have_real pero el pin dice \$pinned_real." >&2
    fi
fi

exec "\$VENV/bin/python" -m monitor "\$@"
EOF
    chmod +x "$BIN"
}

# Si hay algo en $BIN que no es nuestro, lo respaldamos antes de pisarlo.
prepare_bin() {
    mkdir -p "$(dirname "$BIN")"
    [ -e "$BIN" ] || [ -L "$BIN" ] || return 0
    if grep -qF "$WRAPPER_MARKER" "$BIN" 2>/dev/null; then
        return 0 # es nuestro wrapper: se sobrescribe
    fi
    if [ -L "$BIN" ]; then
        local link
        link="$(readlink -f "$BIN" 2>/dev/null || true)"
        case "$link" in
            "$VENV"/*)
                # Symlink viejo de la instalación anterior. Hay que BORRAR el
                # enlace, no solo dejar pasar: `cat > $BIN` escribe atravesando
                # symlinks, así que sin esto el wrapper se endosaba sobre el
                # console script de pip dentro del .venv y ~/.local/bin/monitor
                # seguía siendo un symlink en vez del wrapper.
                rm -f "$BIN"
                return 0
                ;;
        esac
    fi
    local backup="$BIN.bak.$(date +%Y%m%d%H%M%S)"
    mv "$BIN" "$backup"
    echo "  ↳ binario previo respaldado en $backup"
}

# Append idempotente al rc del shell de login. La versión anterior solo avisaba y
# nunca escribía, así que un usuario sin ~/.local/bin en PATH terminaba con
# "command not found" después de un install exitoso.
ensure_path() {
    local rc
    if [ -n "${PC_MONITOR_RC:-}" ]; then
        rc="$PC_MONITOR_RC"
    elif [ -n "${ZDOTDIR:-}" ] && [ -f "${ZDOTDIR}/.zshrc" ]; then
        rc="${ZDOTDIR}/.zshrc"
    elif [ -f "$HOME/.zshrc" ]; then
        rc="$HOME/.zshrc"
    else
        rc="$HOME/.bashrc"
    fi
    [ -f "$rc" ] || touch "$rc"
    if grep -qF '.local/bin' "$rc"; then
        return 0
    fi
    {
        printf '\n# pc-monitor: comandos de usuario\n'
        printf 'export PATH="$HOME/.local/bin:$PATH"\n'
    } >>"$rc"
    echo "  ↳ ~/.local/bin agregado al PATH en $rc"
}

# ── Prerrequisitos ──
command -v git >/dev/null 2>&1 || die "git no está instalado"

# ── Obtener/actualizar el código ──
echo "▶ pc-monitor — instalando en $TARGET"
if [ -d "$TARGET/.git" ]; then
    echo "  ↳ ya existe, actualizando..."
    git -C "$TARGET" pull --ff-only
elif [ -d "$TARGET" ]; then
    echo "  ↳ existe pero no es un repo, respaldando como pc-monitor.bak..."
    mv "$TARGET" "$TARGET.bak"
    git clone "$REPO_URL" "$TARGET"
else
    mkdir -p "$(dirname "$TARGET")"
    git clone "$REPO_URL" "$TARGET"
fi

# ── Intérprete pineado ──
# El pin se reescribe SIEMPRE: si el intérprete pineado murió (upgrade del SO que
# lo borró) hay que apuntar al nuevo, o el chequeo de venv_ok de abajo compara
# contra un pin viejo y da falso negativo.
PY="$(pick_python)" || die "no hay un /usr/bin/python3.X entre 3.$MIN_MINOR y 3.$((MAX_MINOR - 1))"
if [ -f "$PINNED" ] && [ "$(cat "$PINNED")" = "$PY" ]; then
    echo "  ↳ intérprete pineado: $PY (reusado)"
else
    if [ -f "$PINNED" ]; then
        echo "  ↳ intérprete pineado: $PY (cambió: $(cat "$PINNED"))"
    else
        echo "  ↳ intérprete pineado: $PY"
    fi
    printf '%s\n' "$PY" >"$PINNED"
fi

# ── Entorno virtual + paquete editable (solo stdlib, sin deps externas) ──
if venv_ok; then
    echo "  ↳ venv sano ($(py_minor "$VENV/bin/python")) — se reusa"
else
    if [ -d "$VENV" ]; then
        echo "  ↳ venv roto, desalineado o anclado al alias flotante — recreando con $PY"
        rm -rf "$VENV"
    fi
    create_venv "$PY"
    venv_ok || die "el venv se creó pero monitor no se importa — revisá $VENV"
    echo "  ↳ venv creado con $PY"
fi

# ── Ejecutable ──
prepare_bin
write_wrapper
ensure_path

# ── Smoke test: si esto falla, no declaramos éxito ──
if ! out="$("$BIN" --version 2>&1)"; then
    printf '%s\n' "$out" >&2
    die "instalación incompleta: '$BIN --version' falló"
fi

echo ""
echo "✅ pc-monitor instalado. Ejecutá:  monitor"
echo "   Versión:    $out"
echo "   Código:     $TARGET"
echo "   Intérprete: $PY (pineado en $(basename "$PINNED"))"
echo "   Datos:      $HOME/.config/monitor/ (intactos)"
echo "   Comandos: monitor · monitor --update · monitor --check-update · monitor --uninstall · monitor --version"
