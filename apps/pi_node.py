"""Raspberry Pi node: hardware I/O (sensors, actuators, dispatching).

Composition root for the Pi side. It assembles the Pi's Components - actuator
drivers, plan dispatch, and reactive gate safety - wires them to the broker, and starts
them through the uniform `Component` lifecycle (`start()` / `stop()`).

Sensors are the one piece that needs real hardware. By default this runs the
hardware-free `SimulatedSensors` and plays a short scripted scenario, so you can
run it with no hardware and watch the laptop react over the broker.
`PARKING_SENSORS=hardware` selects the Grove/RC522 driver skeletons, which remain
inert until their `TODO` hardware loops are implemented, plus the live
`DistanceSensor`, which reads the Mega's serial `DISTANCE ...` lines for real.

    python apps/pi_node.py
    PARKING_BROKER_HOST=192.168.0.10 python apps/pi_node.py     # broker on the laptop
    PARKING_SENSORS=hardware python apps/pi_node.py             # on the real Pi
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parking.common import load_settings  # noqa: E402
from parking.common import models as m  # noqa: E402
from parking.common.messaging import MqttBus  # noqa: E402
from parking.actuators import BufferLed, GateServo, VehicleMover  # noqa: E402
from parking.dispatching import GateSafetyController, PlanDispatcher  # noqa: E402
from parking.sensors import DistanceSensor, DurationDial, GateMotionSensor, NfcReader, OccupancySensor  # noqa: E402
from parking.simulation import SimulatedSensors  # noqa: E402

REGISTERED_CARD = "AB12CD34"
PARKING_SPOTS = ["P1", "P2", "P3"]


def pi_components(bus: MqttBus) -> list:
    """The Pi's always-on Components: actuator drivers + the gate controller.

    The actuator drivers are no-ops until real hardware is attached, but the
    controller and all the bus wiring are live.
    """
    return [
        GateServo(bus),
        BufferLed(bus),
        VehicleMover(bus),
        PlanDispatcher(bus),
        GateSafetyController(bus),
    ]


def play_scenario(bus: MqttBus) -> None:
    """Drive one complete arrival, parking, checkout, and departure cycle."""
    sensors = SimulatedSensors(bus)
    time.sleep(1.0)

    print("[pi] driver selects 25 minutes, arrives, and scans at the gate")
    sensors.turn_dial(25)
    sensors.car_arrives_at_gate()
    time.sleep(1.0)
    sensors.scan_nfc(REGISTERED_CARD)
    time.sleep(1.0)

    print("[pi] admitted car enters B1; gate then clears")
    sensors.car_parks("B1")
    time.sleep(1.0)
    sensors.gate_clear()
    time.sleep(1.0)

    print("[pi] car moves from B1 to assigned spot P1")
    sensors.car_leaves("B1")
    sensors.car_parks("P1")
    time.sleep(1.0)

    print("[pi] customer checks out; car is retrieved to B1")
    sensors.scan_nfc(REGISTERED_CARD, reader=m.READER_CHECKOUT)
    time.sleep(1.0)
    sensors.car_leaves("P1")
    sensors.car_parks("B1")
    time.sleep(1.0)

    print("[pi] customer drives out; buffer and gate clear")
    sensors.car_arrives_at_gate()
    time.sleep(1.0)
    sensors.car_leaves("B1")
    sensors.gate_clear()
    time.sleep(1.0)
    print("\n[pi] done.")


def run_hardware_sensors(bus: MqttBus) -> None:
    """Start the hardware-driver skeletons and wait for events."""
    sensors = [OccupancySensor(bus, spot) for spot in PARKING_SPOTS] + [
        GateMotionSensor(bus),
        NfcReader(bus, reader=m.READER_GATE),
        NfcReader(bus, reader=m.READER_CHECKOUT),
        DurationDial(bus),
        DistanceSensor(bus),
    ]
    for sensor in sensors:
        sensor.start()
    print(
        "[pi] hardware sensors started; distance ranger is live over serial, "
        "the rest remain TODO skeletons emitting no events. Ctrl-C to stop."
    )
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for sensor in sensors:
            sensor.stop()


def main() -> None:
    s = load_settings()
    bus = MqttBus(host=s.broker_host, port=s.broker_port, client_id="pi")

    components = pi_components(bus)
    # Echo gate commands so the gate's behaviour is visible even with no motor.
    bus.subscribe_message(m.GateCommand.TOPIC, lambda msg: print(f"[pi] gate motor -> {msg.action}"))
    for c in components:
        c.start()

    bus.start()
    print(f"[pi] connected to broker {s.broker_host}:{s.broker_port}.\n")

    if os.environ.get("PARKING_SENSORS", "sim") == "hardware":
        run_hardware_sensors(bus)
    else:
        play_scenario(bus)

    for c in components:
        c.stop()
    bus.stop()


if __name__ == "__main__":
    main()
