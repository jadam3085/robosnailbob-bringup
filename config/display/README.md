# RoboSnailBob — Display & VNC Headless Setup

## Problem

The NAD9 (Intel Iris Xe) running Ubuntu 24.04 + GDM3 has a quirky display situation:

- **HDMI-2**: Real monitor, full EDID, supports up to 2560×1440
- **HDMI-1**: Ghost/fallback output with no EDID — defaults to 1024×768 max
- **VirtualHeads** (modesetting driver option): Not supported on this driver version — silently ignored
- **RealVNC Service Mode**: Connects via cloud relay but requires a live graphical session to attach to

Without a monitor plugged in, GDM either doesn't start a proper session or GNOME loses its render target, causing RealVNC's agent to fail (`AgentInitCheck: no response from agent`).

## Solution

Force HDMI-1 to accept a 1920×1080 modeline (which it otherwise refuses due to missing EDID), then mirror both outputs. This gives RealVNC a stable 1920×1080 desktop regardless of whether a physical monitor is present.

### Why mirroring instead of switching?

Mirroring both outputs means:
- RealVNC always has something to render, even mid-hotplug
- No state machine needed to track which output is "active"
- Simpler, fewer edge cases

Tradeoff: the physical monitor runs at 1080p instead of its native 1440p while mirroring. Acceptable for a robot operator interface.

## Key Files

| File | Deployed to | Purpose |
|------|-------------|---------|
| `fix-display.sh` | `~/fix-display.sh` | Injects mode + applies mirror |
| `fix-display.desktop` | `~/.config/autostart/` | Runs fix-display.sh at login |
| `display-hotplug.sh` | `/usr/local/bin/` | Re-runs fix on monitor plug/unplug |
| `99-display-hotplug.rules` | `/etc/udev/rules.d/` | udev trigger for DRM change events |
| `gdm3-custom.conf` | `/etc/gdm3/custom.conf` | Auto-login + disable Wayland |
| `x11vnc.service` | `/etc/systemd/system/` | Backup VNC on port 5900 |

## Critical Gotchas

### GDM config comments MUST start with `#`
A missing `#` on any comment line causes GDM to silently ignore the entire file.
Symptoms: auto-login stops working, Wayland comes back, VNC agent fails.
This is a hard-learned lesson — do not add bare comment text to `/etc/gdm3/custom.conf`.

### VirtualHeads does not work
The modesetting driver on this system logs:
```
(WW) modeset(0): Option "VirtualHeads" is not used
```
Do not attempt to re-enable it. The xrandr modeline injection approach is the correct solution.

### xserver-xorg-video-dummy breaks Xorg on this hardware
Tested and reverted. The dummy driver config interferes with the modesetting pipeline on Intel Iris Xe + GDM3, preventing proper session startup. Do not reintroduce it.

### HDMI output names
Confirmed on this hardware:
- `HDMI-1` — no EDID, virtual/fallback
- `HDMI-2` — real monitor

If hardware changes, run `DISPLAY=:0 xrandr` to confirm output names and update scripts accordingly.

## VNC Setup

**Primary:** RealVNC Server (service mode, cloud relay via RealVNC Connect team)
- Service: `vncserver-x11-serviced`
- Connect via RealVNC Viewer using team/cloud relay

**Fallback:** x11vnc on port 5900
- Connect directly: `<robot-ip>:5900`
- Password stored at `~/.vnc/passwd`

## Restore from Scratch

```bash
git clone https://github.com/jadam3085/<repo>.git
cd <repo>/config
bash setup.sh
sudo reboot
```
