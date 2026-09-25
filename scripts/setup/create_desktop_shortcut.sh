#!/bin/bash
#
# Creates a Desktop shortcut that launches PRISM Studio with the app icon
# (macOS/Linux counterpart of create_desktop_shortcut.ps1).
#
#   macOS: "PRISM Studio.command" (opens in Terminal), icon from PrismStudio.icns
#   Linux: "prism-studio.desktop" launcher, icon from MRI_Lab_Logo.png
#
# Runs prism-studio.py from the repository's .venv, so the shortcut keeps
# working after updates. Re-running this overwrites the existing shortcut.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"

if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
    echo "ERROR: $REPO_ROOT/.venv not found. Run install.sh first." >&2
    exit 1
fi
if [ ! -d "$DESKTOP" ]; then
    echo "WARNING: Desktop folder '$DESKTOP' not found; no shortcut created." >&2
    exit 1
fi

if [ "$(uname)" = "Darwin" ]; then
    LINK="$DESKTOP/PRISM Studio.command"
    cat > "$LINK" <<EOF
#!/bin/bash
cd "$REPO_ROOT" || exit 1
TTY_DEV="\$(tty)"
.venv/bin/python prism-studio.py "\$@"
# Close this Terminal window once PRISM exits (only this window, matched by tty).
(sleep 1; osascript -e "tell application \"Terminal\" to close (every window whose tty of selected tab is \"\$TTY_DEV\")") >/dev/null 2>&1 &
EOF
    chmod +x "$LINK"
    # Custom Finder icon; cosmetic, so a failure only loses the icon.
    osascript -l JavaScript - "$REPO_ROOT/PrismStudio.icns" "$LINK" >/dev/null 2>&1 <<'JXA' ||
function run(argv) {
    ObjC.import('AppKit');
    const img = $.NSImage.alloc.initWithContentsOfFile(argv[0]);
    $.NSWorkspace.sharedWorkspace.setIconForFileOptions(img, argv[1], 0);
}
JXA
        echo "WARNING: Could not set the shortcut icon." >&2
else
    LINK="$DESKTOP/prism-studio.desktop"
    cat > "$LINK" <<EOF
[Desktop Entry]
Type=Application
Name=PRISM Studio
Comment=Launch PRISM Studio
Exec="$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/prism-studio.py"
Path=$REPO_ROOT
Icon=$REPO_ROOT/app/static/img/MRI_Lab_Logo.png
Terminal=true
Categories=Science;
EOF
    chmod +x "$LINK"
    # GNOME refuses to launch untrusted .desktop files from the Desktop.
    gio set "$LINK" metadata::trusted true >/dev/null 2>&1 || true
fi

echo "Desktop shortcut created: $LINK"
