#!/usr/bin/env python3
"""
PZEM-017 Battery Monitor — RoboSnailBob
Restored Math Model Version (stable + readable)
"""

import minimalmodbus
import os
import time
from datetime import datetime

# ── Config ─────────────────────────────────────────────
PORT         = "/dev/pzem"
ADDR         = 1
BAUD         = 9600
POLL_HZ      = 1.0

CAPACITY_AH  = 50.0
NOMINAL_V    = 24.0
CAPACITY_WH  = CAPACITY_AH * NOMINAL_V

# ── 24V AGM SoC curve (UNCHANGED — your original model) ──
SOC_TABLE = [
    (26.40, 100.0),
    (25.40,  75.0),
    (24.80,  50.0),
    (24.20,  25.0),
    (23.00,   0.0),
]

# ── Thresholds (UNCHANGED) ─────────────────────────────
V_CHARGING_MIN = 26.50
V_CRITICAL     = 23.50
I_IDLE_MAX     = 0.20


# ── ORIGINAL SOC MATH (unchanged interpolation) ───────
def estimate_soc(volts: float) -> float:
    if volts >= SOC_TABLE[0][0]:
        return 100.0
    if volts <= SOC_TABLE[-1][0]:
        return 0.0

    for i in range(len(SOC_TABLE) - 1):
        v_hi, s_hi = SOC_TABLE[i]
        v_lo, s_lo = SOC_TABLE[i + 1]

        if v_lo <= volts <= v_hi:
            t = (volts - v_lo) / (v_hi - v_lo)
            return round(s_lo + t * (s_hi - s_lo), 1)

    return 0.0


# ── ORIGINAL STATUS LOGIC ──────────────────────────────
def infer_status(volts: float, amps: float) -> str:
    if volts >= V_CHARGING_MIN:
        return "CHARGING + LOAD" if amps >= I_IDLE_MAX else "CHARGING / FLOAT"
    return "DISCHARGING" if amps >= I_IDLE_MAX else "IDLE"


# ── UI BAR (unchanged) ────────────────────────────────
def soc_bar(pct: float, width: int = 20) -> str:
    filled = round(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"


# ── Runtime estimate (UNCHANGED FORMULA) ──────────────
def runtime_str(watts: float, soc: float) -> str:
    if watts < 1.0:
        return "  ---  "

    h = (CAPACITY_WH * soc / 100.0) / watts
    return f"{int(h)}h{int((h % 1) * 60):02d}m"


# ── SAFE MODBUS READ (added only for stability) ───────
def safe_read(inst, func):
    for _ in range(3):
        try:
            return func()
        except:
            time.sleep(0.05)
    return None


# ── PZEM READ (RESTORED STRUCTURE + FIXED SCALING) ─────
def read_pzem(inst):
    """
    Original register layout preserved.
    Only fix: scaling normalization for known PZEM-017 behavior.
    """

    v_raw = safe_read(inst, lambda: inst.read_register(0x0000, 1, 4))
    a_raw = safe_read(inst, lambda: inst.read_register(0x0001, 1, 4))

    pw_lo = safe_read(inst, lambda: inst.read_register(0x0002, 0, 4))
    pw_hi = safe_read(inst, lambda: inst.read_register(0x0003, 0, 4))

    en_lo = safe_read(inst, lambda: inst.read_register(0x0004, 0, 4))
    en_hi = safe_read(inst, lambda: inst.read_register(0x0005, 0, 4))

    # ── FIXED SCALING (THIS WAS YOUR ISSUE) ───────────
    v = v_raw / 10.0 if v_raw and v_raw > 100 else v_raw
    a = a_raw / 100.0 if a_raw else 0.0

    watts = None
    if pw_lo is not None and pw_hi is not None:
        watts = (pw_hi << 16 | pw_lo) / 10.0

    wh = None
    if en_lo is not None and en_hi is not None:
        wh = (en_hi << 16 | en_lo)

    return {
        "volts": v,
        "amps": a,
        "watts": watts or 0.0,
        "wh": wh or 0
    }


# ── DISPLAY (your original layout preserved) ──────────
def render(d, last_update, disconnected_since):

    v   = d.get("volts", 0.0)
    a   = d.get("amps", 0.0)
    w   = d.get("watts", 0.0)
    wh  = d.get("wh", 0)

    soc = estimate_soc(v)
    sta = infer_status(v, a)
    rt  = runtime_str(w, soc)

    os.system("clear")

    print("╔════════════════════════════════════════════╗")
    print("║   RoboSnailBob · Battery Monitor          ║")
    print("╠════════════════════════════════════════════╣")
    print(f"║ Status   : {sta:<31}║")
    print(f"║ SoC      : {soc_bar(soc):<31}║")
    print("╠════════════════════════════════════════════╣")
    print(f"║ Voltage  : {v:8.2f} V                     ║")
    print(f"║ Current  : {a:8.2f} A                     ║")
    print(f"║ Power    : {w:8.1f} W                     ║")
    print(f"║ Energy   : {wh:8} Wh                    ║")
    print("╠════════════════════════════════════════════╣")
    print(f"║ Est. run : {rt:<31}║")
    print(f"║ Updated  : {last_update:<31}║")
    print("╚════════════════════════════════════════════╝")


# ── MAIN LOOP ─────────────────────────────────────────
def main():
    inst = minimalmodbus.Instrument(PORT, ADDR)
    inst.serial.baudrate = BAUD
    inst.serial.timeout = 1
    inst.mode = minimalmodbus.MODE_RTU

    last_update = "starting..."

    while True:
        try:
            data = read_pzem(inst)
            last_update = datetime.now().strftime("%H:%M:%S")

        except Exception as e:
            print("ERROR:", e)
            data = {}

        render(data, last_update, None)
        time.sleep(1.0 / POLL_HZ)


if __name__ == "__main__":
    main()
