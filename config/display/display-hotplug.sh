#!/bin/bash
# display-hotplug.sh
# Called by udev rule (99-display-hotplug.rules) on DRM connector change events.
# Re-applies the display fix after monitor plug/unplug events.

export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

sleep 2  # Let X settle after hotplug event

# Re-apply fix-display logic
/home/jadam/fix-display.sh
