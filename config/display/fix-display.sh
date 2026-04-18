#!/bin/bash
# fix-display.sh
# Injects a 1920x1080 mode into HDMI-1 (which has no EDID and defaults to 1024x768)
# and mirrors both displays at 1920x1080 for stable RealVNC headless operation.
#
# Run automatically at login via fix-display.desktop autostart entry.
# Safe to run manually at any time.

export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

# Create mode (safe - ignores error if already exists)
xrandr --newmode "1920x1080_60" 173.00 1920 2048 2248 2576 1080 1083 1088 1120 -hsync +vsync 2>/dev/null

# Attach mode to HDMI-1 (the virtual/fallback display with no EDID)
xrandr --addmode HDMI-1 1920x1080_60 2>/dev/null

# Apply resolution to both displays
xrandr --output HDMI-1 --mode 1920x1080_60
xrandr --output HDMI-2 --mode 1920x1080

# Mirror: HDMI-1 follows HDMI-2
xrandr --output HDMI-1 --same-as HDMI-2

echo "Display fix applied: HDMI-1 and HDMI-2 mirrored at 1920x1080"
