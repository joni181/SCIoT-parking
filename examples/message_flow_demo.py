"""Runnable walkthrough of the two driving scenarios - no hardware, no broker.

    python examples/message_flow_demo.py

It wires a `MemoryBus`, attaches a tracer that prints every message as it flows,
and then plays out:

  Scenario 1: a light sensor reports that a car parked in spot P1, and the
              laptop side (storage/viz stand-in) sees it.
  Scenario 2: a car arrives at the gate and a registered card is scanned, so
              the control logic opens the gate; when the car passes, it closes.

Swap `MemoryBus()` for `MqttBus(host=...)` and the exact same code runs over a
real MQTT broker across the Pi and the laptop.
"""
from __future__ import annotations

import json
import os
import sys

# Allow running directly (python examples/message_flow_demo.py) without install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parking.common import topics  # noqa: E402
from parking.common.messaging import MemoryBus  # noqa: E402
from parking.simulation import (  # noqa: E402
    OccupancyTracker,
    ReactiveGateController,
    RecordingActuators,
    SimulatedSensors,
)

REGISTERED_CARD = "AB12CD34"
PARKING_SPOTS = ["P1", "P2", "P3"]


def tracer(topic: str, payload: bytes) -> None:
    env = json.loads(payload)
    print(f"   bus | {topic:24} | {env['type']:14} | {env['data']}")


def main() -> None:
    bus = MemoryBus()
    bus.subscribe(topics.ALL, tracer)  # watch everything that crosses the bus

    # Laptop side: storage/viz stand-in.
    tracker = OccupancyTracker(bus)
    # Pi side: control logic + actuators.
    gate = ReactiveGateController(bus, known_uids=[REGISTERED_CARD])
    actuators = RecordingActuators(bus)
    # Pi side: the sensors (here, simulated).
    sensors = SimulatedSensors(bus)

    print("\n=== Scenario 1: a car parks in spot P1 ===")
    print(" (light sensor on the Pi -> bus -> laptop storage/viz)")
    sensors.car_parks("P1", raw_value=820)
    print(f"   => laptop sees P1 occupied: {tracker.is_occupied('P1')}")
    print(f"   => free spots now: {tracker.free_spots(PARKING_SPOTS)}")

    print("\n=== Scenario 2: a registered car arrives at the gate ===")
    print(" (motion + NFC on the Pi -> bus -> control logic -> gate motor)")
    sensors.car_arrives_at_gate()
    print(f"   gate after motion only (no card yet): {actuators.gate_state}")
    sensors.scan_nfc(REGISTERED_CARD)
    print(f"   => gate after registered card scanned: {actuators.gate_state}")
    sensors.gate_clear()
    print(f"   => gate after the car drove through:   {actuators.gate_state}")

    print("\n=== Negative check: an unknown card does NOT open the gate ===")
    actuators.gate_commands.clear()
    sensors.car_arrives_at_gate()
    sensors.scan_nfc("DEADBEEF")
    print(f"   => gate state with unknown card: {actuators.gate_state}")

    print("\nDone.")


if __name__ == "__main__":
    main()
