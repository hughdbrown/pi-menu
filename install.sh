#!/usr/bin/env bash
#
# Install the Pi Menu apps into the Raspberry Pi desktop menu.
#
#   ./install.sh              install or upgrade
#   ./install.sh --uninstall  remove everything this script created
#   ./install.sh --no-prompt  never ask; fail instead if something is missing
#
# Everything lands under your home directory. No system files are touched
# except the apt packages and group membership you are asked about.

set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

PREFIX="${PI_MENU_PREFIX:-$HOME/.local/share/pi-menu}"
VENV="$PREFIX/venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
CONFIG_DIR="$HOME/.config/pi-menu"

COMMANDS=(pi-menu pi-life pi-imgshow pi-menu-doctor pi-menu-flash)
DESKTOP_FILES=(pi-menu.desktop pi-life.desktop pi-imgshow.desktop)

PROMPT=1

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

confirm() {
    # Yes/no question, defaulting to yes. Declines when there is no terminal.
    local question="$1"
    if [ "$PROMPT" -eq 0 ] || [ ! -t 0 ]; then
        return 1
    fi
    read -r -p "$question [Y/n] " answer
    case "$answer" in
        [nN]*) return 1 ;;
        *)     return 0 ;;
    esac
}

# ---------------------------------------------------------------- uninstall

uninstall() {
    say "Removing desktop entries"
    for entry in "${DESKTOP_FILES[@]}"; do
        rm -fv "$DESKTOP_DIR/$entry"
    done

    say "Removing launcher links"
    for command in "${COMMANDS[@]}"; do
        rm -fv "$BIN_DIR/$command"
    done

    if [ -d "$PREFIX" ]; then
        say "Removing $PREFIX"
        rm -rf "$PREFIX"
    fi

    rm -rf "$HOME/.cache/pi-menu"

    if [ -d "$CONFIG_DIR" ]; then
        warn "left $CONFIG_DIR in place — it holds your own app list"
    fi

    refresh_menu
    say "Uninstalled."
}

# ------------------------------------------------------------ prerequisites

find_python() {
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done
    die "python3 not found"
}

apt_install() {
    # Offer to install missing Debian packages, or explain how.
    local packages=("$@")
    if ! command -v apt-get >/dev/null 2>&1; then
        die "missing: ${packages[*]} — install them with your package manager"
    fi
    say "These packages are missing: ${packages[*]}"
    if confirm "Install them now with sudo apt-get?"; then
        sudo apt-get update
        sudo apt-get install -y "${packages[@]}"
    else
        die "run: sudo apt-get install -y ${packages[*]}"
    fi
}

check_prerequisites() {
    local python="$1"
    local missing=()

    "$python" -c 'import venv' >/dev/null 2>&1 || missing+=(python3-venv)
    "$python" -c 'import tkinter' >/dev/null 2>&1 || missing+=(python3-tk)

    if [ "${#missing[@]}" -gt 0 ]; then
        apt_install "${missing[@]}"
        "$python" -c 'import tkinter' >/dev/null 2>&1 \
            || die "tkinter still unavailable after installing python3-tk"
    fi
}

check_serial_group() {
    # The Pico shows up as /dev/ttyACM0, owned by group dialout.
    if id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then
        return
    fi
    say "You are not in the 'dialout' group, so opening the Stellar Unicorn will fail."
    if confirm "Add $USER to the dialout group?"; then
        sudo usermod -a -G dialout "$USER"
        warn "log out and back in for the new group to take effect"
    else
        warn "run: sudo usermod -a -G dialout $USER"
    fi
}

# ---------------------------------------------------------------- installing

install_package() {
    local python="$1"

    if [ ! -x "$VENV/bin/python" ]; then
        say "Creating a virtual environment in $VENV"
        mkdir -p "$PREFIX"
        "$python" -m venv "$VENV"
    else
        say "Reusing the virtual environment in $VENV"
    fi

    say "Installing pi-menu and its dependencies"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --upgrade --prefer-binary "$SOURCE_DIR"

    "$VENV/bin/python" -c 'import tkinter' >/dev/null 2>&1 \
        || die "the virtual environment cannot see tkinter; try deleting $VENV and rerunning"
}

link_commands() {
    say "Linking commands into $BIN_DIR"
    mkdir -p "$BIN_DIR"
    for command in "${COMMANDS[@]}"; do
        ln -sfn "$VENV/bin/$command" "$BIN_DIR/$command"
        printf '    %s -> %s\n' "$BIN_DIR/$command" "$VENV/bin/$command"
    done

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) warn "$BIN_DIR is not on your PATH; the menu entries still work" ;;
    esac
}

write_desktop_entry() {
    local filename="$1" name="$2" comment="$3" exec_line="$4"
    local icon="$5" categories="$6" terminal="$7"

    cat > "$DESKTOP_DIR/$filename" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$name
Comment=$comment
Exec=$exec_line
Icon=$icon
Terminal=$terminal
Categories=$categories
StartupNotify=true
EOF
    printf '    %s\n' "$DESKTOP_DIR/$filename"
}

install_desktop_entries() {
    say "Writing desktop entries"
    mkdir -p "$DESKTOP_DIR"

    write_desktop_entry pi-menu.desktop \
        "Pi Menu" \
        "Launch Stellar Unicorn applications" \
        "$VENV/bin/pi-menu" \
        applications-utilities \
        "Utility;" \
        false

    # These two run with Terminal=true so that starting them straight from
    # the Pi menu still shows the connection messages, exactly as it does
    # when Pi Menu launches them.
    write_desktop_entry pi-life.desktop \
        "Game of Life (Stellar Unicorn)" \
        "Conway's Game of Life on a 16x16 LED panel" \
        "$VENV/bin/pi-life" \
        applications-games \
        "Game;Simulation;" \
        true

    write_desktop_entry pi-imgshow.desktop \
        "Image Shower (Stellar Unicorn)" \
        "Show an image file on a 16x16 LED panel" \
        "$VENV/bin/pi-imgshow" \
        image-x-generic \
        "Graphics;Viewer;" \
        true
}

install_user_config() {
    mkdir -p "$CONFIG_DIR"
    if [ -f "$CONFIG_DIR/apps.json" ]; then
        say "Keeping your existing $CONFIG_DIR/apps.json"
    else
        say "Copying the default app list to $CONFIG_DIR/apps.json"
        cp "$SOURCE_DIR/src/pi_menu/apps.json" "$CONFIG_DIR/apps.json"
    fi
}

offer_to_flash() {
    # The Pico needs its own copy of the frame server. Skipping this is
    # the single most common reason the panel stays dark.
    say "The Stellar Unicorn needs the frame server copied onto it."
    if confirm "Copy it now over USB?"; then
        "$VENV/bin/pi-menu-flash" || warn "flashing failed; run pi-menu-flash to retry"
    else
        warn "run pi-menu-flash later, or the panel will not light up"
    fi
}

refresh_menu() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
    fi
    # LXDE rebuilds its menu when the applications directory changes; give
    # it a nudge in case the panel is caching.
    if command -v lxpanelctl >/dev/null 2>&1; then
        lxpanelctl restart >/dev/null 2>&1 || true
    fi
}

# --------------------------------------------------------------------- main

main() {
    local action=install
    for argument in "$@"; do
        case "$argument" in
            --uninstall) action=uninstall ;;
            --no-prompt) PROMPT=0 ;;
            -h|--help)
                sed -n '3,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
                return 0
                ;;
            *) die "unknown option: $argument (try --help)" ;;
        esac
    done

    if [ "$action" = uninstall ]; then
        uninstall
        return 0
    fi

    [ -f "$SOURCE_DIR/pyproject.toml" ] \
        || die "run this script from inside the pi-menu source directory"

    local python
    python="$(find_python)"
    say "Using $("$python" --version 2>&1)"

    check_prerequisites "$python"
    install_package "$python"
    link_commands
    install_desktop_entries
    install_user_config
    check_serial_group
    refresh_menu
    offer_to_flash

    say "Done."
    cat <<EOF

  Look under the Raspberry Pi menu for "Pi Menu", or run one directly:

      pi-menu        the launcher
      pi-life        Conway's Game of Life
      pi-imgshow     the image shower
      pi-menu-flash  copy the frame server onto the panel
      pi-menu-doctor check the link to the panel, layer by layer

  Edit $CONFIG_DIR/apps.json to add your own programs to the menu.

  If the panel stays dark, run pi-menu-doctor. It names the layer that
  broke instead of leaving you guessing.
EOF
}

# Only run when executed. Sourcing the script exposes the functions
# on their own, which is how the tests check the generated files.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
