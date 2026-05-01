#!/usr/bin/env python3
"""
PZEM-017 Battery Monitor Node -- RoboSnailBob
Publishes:
  /battery/state          sensor_msgs/BatteryState
  /battery/voltage        std_msgs/Float32
  /battery/current        std_msgs/Float32
  /battery/power_watts    std_msgs/Float32

Quantum Edge 2.0: 2x 12V AGM in series = 24V nominal, 50Ah
Current note: PZEM shunt measures load magnitude only -- positive always.
"""

import time
import minimalmodbus
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Float32

# BatteryState uint8 constants
PS_STATUS_CHARGING     = 1
PS_STATUS_DISCHARGING  = 2
PS_STATUS_NOT_CHARGING = 3

PS_HEALTH_GOOD         = 1
PS_HEALTH_DEAD         = 3
PS_HEALTH_OVERVOLTAGE  = 4

# 24V AGM SoC table -- resting voltage, no load
SOC_TABLE = [
    (26.40, 1.00),
    (25.40, 0.75),
    (24.80, 0.50),
    (24.20, 0.25),
    (23.00, 0.00),
]


def _estimate_soc(volts: float) -> float:
    if volts >= SOC_TABLE[0][0]:
        return 1.0
    if volts <= SOC_TABLE[-1][0]:
        return 0.0
    for i in range(len(SOC_TABLE) - 1):
        v_hi, s_hi = SOC_TABLE[i]
        v_lo, s_lo = SOC_TABLE[i + 1]
        if v_lo <= volts <= v_hi:
            t = (volts - v_lo) / (v_hi - v_lo)
            return round(s_lo + t * (s_hi - s_lo), 4)
    return 0.0


def _infer_status(volts: float, amps: float, v_chg_min: float, i_idle: float) -> int:
    if volts >= v_chg_min:
        return PS_STATUS_CHARGING
    return PS_STATUS_DISCHARGING if amps >= i_idle else PS_STATUS_NOT_CHARGING


class PzemBatteryNode(Node):

    def __init__(self):
        super().__init__('pzem_battery_node')

        # Parameters -- override via launch args or CLI
        self.declare_parameter('port',            '/dev/pzem')
        self.declare_parameter('modbus_address',  1)
        self.declare_parameter('baud',            9600)
        self.declare_parameter('poll_hz',         1.0)
        self.declare_parameter('capacity_ah',     50.0)
        self.declare_parameter('nominal_voltage', 24.0)
        self.declare_parameter('v_charging_min',  26.50)
        self.declare_parameter('v_critical',      23.50)
        self.declare_parameter('i_idle_max',      0.20)
        self.declare_parameter('frame_id',        'battery')

        port           = self.get_parameter('port').value
        addr           = self.get_parameter('modbus_address').value
        baud           = self.get_parameter('baud').value
        poll_hz        = self.get_parameter('poll_hz').value
        self.cap_ah    = self.get_parameter('capacity_ah').value
        self.nom_v     = self.get_parameter('nominal_voltage').value
        self.v_chg_min = self.get_parameter('v_charging_min').value
        self.v_crit    = self.get_parameter('v_critical').value
        self.i_idle    = self.get_parameter('i_idle_max').value
        self.frame_id  = self.get_parameter('frame_id').value
        self.cap_wh    = self.cap_ah * self.nom_v

        self._disconnected_since: float | None = None

        # Modbus setup
        try:
            self._inst = minimalmodbus.Instrument(port, addr)
            self._inst.serial.baudrate = baud
            self._inst.serial.timeout  = 1
            self._inst.mode = minimalmodbus.MODE_RTU
            self.get_logger().info(f'Modbus connected: {port} addr={addr}')
        except Exception as e:
            self.get_logger().error(f'Modbus init failed: {e}')
            self._inst = None

        # Publishers
        self._pub_state   = self.create_publisher(BatteryState, '/battery/state',      10)
        self._pub_voltage = self.create_publisher(Float32,      '/battery/voltage',     10)
        self._pub_current = self.create_publisher(Float32,      '/battery/current',     10)
        self._pub_power   = self.create_publisher(Float32,      '/battery/power_watts', 10)

        period = 1.0 / max(poll_hz, 0.1)
        self.create_timer(period, self._poll)

        self.get_logger().info(
            f'PZEM battery node ready -- {self.cap_ah:.0f}Ah/{self.cap_wh:.0f}Wh @ {poll_hz}Hz'
        )

    def _read_registers(self) -> dict:
        inst  = self._inst
        v     = inst.read_register(0x0000, 2, 4)
        a     = inst.read_register(0x0001, 2, 4)
        pw_lo = inst.read_register(0x0002, 0, 4)
        pw_hi = inst.read_register(0x0003, 0, 4)
        en_lo = inst.read_register(0x0004, 0, 4)
        en_hi = inst.read_register(0x0005, 0, 4)
        return dict(
            volts = v,
            amps  = a,
            watts = (pw_hi << 16 | pw_lo) / 10.0,
            wh    = float(en_hi << 16 | en_lo),
        )

    def _poll(self) -> None:
        if self._inst is None:
            self.get_logger().warn(
                'No Modbus instrument -- skipping poll',
                throttle_duration_sec=10
            )
            return

        try:
            d = self._read_registers()
        except Exception as e:
            if self._disconnected_since is None:
                self._disconnected_since = time.monotonic()
            gap = int(time.monotonic() - self._disconnected_since)
            self.get_logger().warn(
                f'PZEM read failed (no conn {gap}s): {e}',
                throttle_duration_sec=5
            )
            return

        if self._disconnected_since is not None:
            gap = int(time.monotonic() - self._disconnected_since)
            self.get_logger().info(f'PZEM reconnected after {gap}s')
            self._disconnected_since = None

        v   = d['volts']
        a   = d['amps']
        w   = d['watts']
        soc = _estimate_soc(v)
        sta = _infer_status(v, a, self.v_chg_min, self.i_idle)

        if v < self.v_crit:
            health = PS_HEALTH_DEAD
            self.get_logger().warn(
                f'LOW BATTERY: {v:.2f}V -- return to charge!',
                throttle_duration_sec=30
            )
        elif v > 30.0:
            health = PS_HEALTH_OVERVOLTAGE
            self.get_logger().warn(f'OVERVOLTAGE: {v:.2f}V', throttle_duration_sec=30)
        else:
            health = PS_HEALTH_GOOD

        msg                         = BatteryState()
        msg.header.stamp            = self.get_clock().now().to_msg()
        msg.header.frame_id         = self.frame_id
        msg.voltage                 = float(v)
        msg.current                 = float(a)
        msg.charge                  = float(self.cap_ah * soc)
        msg.capacity                = float(self.cap_ah)
        msg.design_capacity         = float(self.cap_ah)
        msg.percentage              = float(soc)
        msg.power_supply_status     = sta
        msg.power_supply_health     = health
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_UNKNOWN
        msg.present                 = True

        self._pub_state.publish(msg)
        self._pub_voltage.publish(Float32(data=float(v)))
        self._pub_current.publish(Float32(data=float(a)))
        self._pub_power.publish(Float32(data=float(w)))


def main(args=None):
    rclpy.init(args=args)
    node = PzemBatteryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
