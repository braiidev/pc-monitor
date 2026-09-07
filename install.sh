#!/usr/bin/env bash
# install.sh — Instala/actualiza pc-monitor (monitor de sistema en consola)
# Uso: curl -fsSL https://raw.githubusercontent.com/braiidev/pc-monitor/main/install.sh | bash
# Instala SIN sudo en ~/.local: código en ~/.local/share/pc-monitor, comando en ~/.local/bin/monitor.
# Configuración personal: vive en ~/.config/monitor y no se toca.

set -euo pipefail

REPO_URL="https://github.com/braiidev/pc-monitor.git"
TARGET="${PC_MONITOR_DIR:-$HOME/.local/share/pc-monitor}"
BIN="$HOME/.local/bin/monitor"

# ── Prerrequisitos ──
for cmd in git python3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: $cmd no está instalado" >&2
        exit 1
    fi
done

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

# ── Entorno virtual + paquete editable (solo stdlib, sin deps externas) ──
python3 -m venv "$TARGET/.venv"
"$TARGET/.venv/bin/pip" install --quiet --upgrade pip
"$TARGET/.venv/bin/pip" install --quiet -e "$TARGET"

# ── Ejecutable global ──
mkdir -p "$HOME/.local/bin"
# Si ya hay un monitor suelto (instalación vieja del monolito), respaldarlo.
if [ -e "$BIN" ] && [ ! -L "$BIN" ]; then
    mv "$BIN" "$BIN.bak"
    echo "  ↳ monitor previo respaldado en $BIN.bak"
fi
ln -sf "$TARGET/.venv/bin/monitor" "$BIN"

echo ""
echo "✅ pc-monitor instalado. Ejecutá:  monitor"
echo "   Código:   $TARGET"
echo "   Datos:    $HOME/.config/monitor/"
echo "   Comando:  monitor (monitor) · monitor --update · monitor --check-update · monitor --uninstall · monitor --version"
if ! echo ":$PATH:" | grep -q ":${HOME}/.local/bin:"; then
    echo "   ⚠ Agregá ~/.local/bin a tu PATH (si no está ya):"
    echo "     echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
fi