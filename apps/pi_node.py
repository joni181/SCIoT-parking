"""Raspberry Pi node: hardware I/O (sensors, actuators, dispatching).

Composition root for the Pi side. It assembles the Pi's Components - actuator
drivers, plan dispatch, and reactive gate safety - wires them to the broker, and starts
them through the uniform `Component` lifecycle (`start()` / `stop()`).

Sensors are the one piece that needs real hardware. By default this runs the
hardware-free `SimulatedSensors` and plays a short scripted scenario, so you can
run it with no hardware and watch the laptop react over the broker.
`PARKING_SENSORS=hardware` opens a `MegaLink` to the Mega's serial port and
selects the real drivers: `DistanceSensor`, `NfcReader`, and one
`OccupancySensor` per spot in `LIGHT_SENSORS` (buffer B1 + P1/P2/P3, one
photoresistor each, see `hardware/pinmap.yaml`) are live over that link,
`GateServo` sends real `GATE OPEN`/`GATE CLOSE` commands over it, and
`DurationDial`/`BufferLed`/`VehicleMover` remain inert until their `TODO`
hardware loops are implemented. There is no gate motion sensor in the
current hardware; `GateSafetyController` closes the gate on a timer instead
(see `parking/dispatching/gate_safety.py`).

    python apps/pi_node.py
    PARKING_BROKER_HOST=192.168.0.10 python apps/pi_node.py     # broker on the laptop
    PARKING_SENSORS=hardware python apps/pi_node.py             # on the real Pi
    PARKING_MEGA_PORT=/dev/ttyACM0 PARKING_SENSORS=hardware python apps/pi_node.py  # override the port
    PARKING_LIGHT_THRESHOLD=650 PARKING_SENSORS=hardware python apps/pi_node.py     # re-tune every spot
    PARKING_LIGHT_THRESHOLD_P2=430 PARKING_SENSORS=hardware python apps/pi_node.py  # re-tune just P2
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parking.common import load_settings  # noqa: E402
from parking.common import models as m  # noqa: E402
from parking.common.messaging import MqttBus  # noqa: E402
from parking.actuators import BufferLed, GateServo, VehicleMover  # noqa: E402
from parking.dispatching import GateSafetyController, PlanDispatcher  # noqa: E402
from parking.mega_link import MegaLink  # noqa: E402
from parking.sensors import DistanceSensor, DurationDial, NfcReader, OccupancySensor  # noqa: E402
from parking.simulation import SimulatedSensors  # noqa: E402

REGISTERED_CARD = "AB12CD34"

# spot_id -> the Mega firmware's label for that spot's photoresistor.
LIGHT_SENSORS = {
    "B1": "photoresistor_a15",
    "P1": "photoresistor_a12",
    "P2": "photoresistor_a13",
    "P3": "photoresistor_a14",
}

# Per-spot midpoint between calibrated empty/covered readings (each mounting
# is different - see hardware/pinmap.yaml and hardware/README.md):
#   B1: ~300 covered / ~860 empty   P1: ~0-5 covered / ~105-112 empty
#   P2: ~284-305 covered / ~780-787 empty   P3: ~58-67 covered / ~633-659 empty
DEFAULT_LIGHT_THRESHOLDS = {
    "B1": 600,
    "P1": 55,
    "P2": 535,
    "P3": 360,
}


def _light_threshold(spot_id: str) -> int:
    """PARKING_LIGHT_THRESHOLD_<spot> overrides PARKING_LIGHT_THRESHOLD, which
    overrides that spot's calibrated default (each photoresistor's
    mounting/wiring calibrates to a different crossover)."""
    fallback = os.environ.get("PARKING_LIGHT_THRESHOLD", str(DEFAULT_LIGHT_THRESHOLDS[spot_id]))
    return int(os.environ.get(f"PARKING_LIGHT_THRESHOLD_{spot_id}", fallback))


def pi_components(bus: MqttBus, link: Optional[MegaLink] = None) -> list:
    """The Pi's always-on Components: actuator drivers + the gate controller.

    The actuator drivers other than the gate are no-ops until real hardware
    is attached, but the controller and all the bus wiring are live. The gate
    servo is live too when `link` is given (hardware mode).
    """
    return [
        GateServo(bus, link=link),
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


def run_hardware_sensors(bus: MqttBus, link: MegaLink) -> None:
    """Start the hardware sensor drivers and wait for events.

    Sensors register their `MegaLink` listeners in `start()`, so they must all
    be started *before* `link.start()` opens the port and begins dispatching
    lines to those listeners.
    """
    sensors = [
        OccupancySensor(bus, spot_id, link, sensor_label=label, threshold=_light_threshold(spot_id))
        for spot_id, label in LIGHT_SENSORS.items()
    ] + [
        NfcReader(bus, link, reader=m.READER_GATE, firmware_reader=1),
        NfcReader(bus, link, reader=m.READER_CHECKOUT, firmware_reader=2),
        DurationDial(bus),
        DistanceSensor(bus, link),
    ]
    for sensor in sensors:
        sensor.start()
    link.start()
    print(
        "[pi] hardware sensors started; distance ranger, NFC readers, and all "
        "4 photoresistors (B1/P1/P2/P3) are live over serial; duration dial "
        "remains a TODO skeleton emitting no events. Ctrl-C to stop."
    )
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        link.stop()
        for sensor in sensors:
            sensor.stop()


def main() -> None:
    s = load_settings()
    bus = MqttBus(host=s.broker_host, port=s.broker_port, client_id="pi")

    hardware_mode = os.environ.get("PARKING_SENSORS", "sim") == "hardware"
    mega_port = os.environ.get("PARKING_MEGA_PORT")
    link = (MegaLink(port=mega_port) if mega_port else MegaLink()) if hardware_mode else None

    components = pi_components(bus, link=link)
    # Echo gate commands so the gate's behaviour is visible even with no motor.
    bus.subscribe_message(m.GateCommand.TOPIC, lambda msg: print(f"[pi] gate motor -> {msg.action}"))
    for c in components:
        c.start()

    bus.start()
    print(f"[pi] connected to broker {s.broker_host}:{s.broker_port}.\n")

    if hardware_mode:
        run_hardware_sensors(bus, link)
    else:
        play_scenario(bus)

    for c in components:
        c.stop()
    bus.stop()


if __name__ == "__main__":
    main()
