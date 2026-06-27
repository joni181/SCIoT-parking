"""Raspberry Pi node: hardware I/O (sensors, actuators, dispatching).

Connects to the broker and, for now, uses the simulation stand-ins and plays a
short scripted scenario - so you can run it with no hardware and watch the
laptop react over the broker. Swap `SimulatedSensors` for the real Grove/RC522
drivers and `RecordingActuators` for the motor/LED drivers as they are built;
the broker wiring stays the same.

    python apps/pi_node.py
    PARKING_BROKER_HOST=192.168.0.10 python apps/pi_node.py   # broker on the laptop
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parking.common import load_settings  # noqa: E402
from parking.common import models as m  # noqa: E402
from parking.common.messaging import MqttBus  # noqa: E402
from parking.simulation import ReactiveGateController, RecordingActuators, SimulatedSensors  # noqa: E402

REGISTERED_CARD = "AB12CD34"


def main() -> None:
    s = load_settings()
    bus = MqttBus(host=s.broker_host, port=s.broker_port, client_id="pi")

    RecordingActuators(bus)  # stand-in for the gate motor / LED
    bus.subscribe_message(m.GateCommand.TOPIC, lambda msg: print(f"[pi] gate motor -> {msg.action}"))
    ReactiveGateController(bus, known_uids=[REGISTERED_CARD])  # stand-in for dispatching
    sensors = SimulatedSensors(bus)

    bus.start()
    print(f"[pi] connected to broker {s.broker_host}:{s.broker_port}; running scenario.\n")
    time.sleep(1.0)

    print("[pi] a car parks in spot P1")
    sensors.car_parks("P1")
    time.sleep(1.0)

    print("[pi] a registered car arrives at the gate and taps its card")
    sensors.car_arrives_at_gate()
    time.sleep(1.0)
    sensors.scan_nfc(REGISTERED_CARD)
    time.sleep(1.0)

    print("[pi] the car drives through the gate")
    sensors.gate_clear()
    time.sleep(1.0)

    print("\n[pi] done.")
    bus.stop()


if __name__ == "__main__":
    main()
