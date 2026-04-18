#!/bin/bash
# setup.sh
# RoboSnailBob system bootstrap — display + VNC headless setup.
# Run once on a fresh Ubuntu 24.04 install to restore the display/VNC configuration.
#
# Usage:
#   git clone https://github.com/jadam3085/<repo>.git
#   cd <repo>/config
#   bash setup.sh
#
# Safe to re-run. All operations are idempotent.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_HOME="/home/jadam"

echo "=== RoboSnailBob System Setup ==="
echo ""

# ── 1. Dependencies ────────────────────────────────────────────────────────────
echo "[1/6] Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y x11-xserver-utils x11vnc

# ── 2. GDM config ──────────────────────────────────────────────────────────────
echo "[2/6] Applying GDM3 config..."
echo ""
echo "  ⚠️  Backing up existing /etc/gdm3/custom.conf to /etc/gdm3/custom.conf.bak"
sudo cp /etc/gdm3/custom.conf /etc/gdm3/custom.conf.bak 2>/dev/null || true
sudo cp "$SCRIPT_DIR/system/gdm3-custom.conf" /etc/gdm3/custom.conf
echo "  ✓ GDM3 config applied"
echo ""
echo "  NOTE: AutomaticLogin is set to 'jadam'."
echo "  If your username differs, edit /etc/gdm3/custom.conf after setup."

# ── 3. Display fix script ──────────────────────────────────────────────────────
echo "[3/6] Installing display fix script..."
cp "$SCRIPT_DIR/display/fix-display.sh" "$USER_HOME/fix-display.sh"
chmod +x "$USER_HOME/fix-display.sh"
echo "  ✓ fix-display.sh installed to $USER_HOME"

# ── 4. Autostart entry ────────────────────────────────────────────────────────
echo "[4/6] Installing autostart entry..."
mkdir -p "$USER_HOME/.config/autostart"
cp "$SCRIPT_DIR/display/fix-display.desktop" "$USER_HOME/.config/autostart/fix-display.desktop"
echo "  ✓ fix-display.desktop installed to ~/.config/autostart"

# ── 5. Hotplug rule ───────────────────────────────────────────────────────────
echo "[5/6] Installing udev hotplug rule..."
sudo cp "$SCRIPT_DIR/display/display-hotplug.sh" /usr/local/bin/display-hotplug.sh
sudo chmod +x /usr/local/bin/display-hotplug.sh
sudo cp "$SCRIPT_DIR/display/99-display-hotplug.rules" /etc/udev/rules.d/99-display-hotplug.rules
sudo udevadm control --reload-rules
echo "  ✓ Hotplug rule installed"

# ── 6. x11vnc service (backup VNC) ────────────────────────────────────────────
echo "[6/6] Installing x11vnc systemd service (backup VNC on port 5900)..."
sudo cp "$SCRIPT_DIR/vnc/x11vnc.service" /etc/systemd/system/x11vnc.service
sudo systemctl daemon-reload
sudo systemctl enable x11vnc

if [ ! -f "$USER_HOME/.vnc/passwd" ]; then
    echo ""
    echo "  ⚠️  No x11vnc password found. Set one now:"
    mkdir -p "$USER_HOME/.vnc"
    x11vnc -storepasswd "$USER_HOME/.vnc/passwd"
else
    echo "  ✓ x11vnc password already set"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Reboot: sudo reboot"
echo "  2. Confirm RealVNC connects headless (primary VNC)"
echo "  3. x11vnc is also available as fallback at <IP>:5900"
echo ""
echo "  If display is wrong after reboot, run manually:"
echo "    DISPLAY=:0 ~/fix-display.sh"
