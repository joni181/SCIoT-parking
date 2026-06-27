"""Laptop node: the compute + UI side (storage, planner, visualization).

Connects to the broker and watches the bus. Right now it wires a stand-in
consumer (`OccupancyTracker`) and prints every message it receives, so you can
literally watch the Pi's events arrive over the network. Replace the stand-ins
with the real storage / planner / visualization modules as they are built - the
broker wiring stays exactly the same.

    python apps/laptop_node.py
    PARKING_BROKER_HOST=192.168.0.10 python apps/laptop_node.py   # broker elsewhere
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parking.common import load_settings, topics  # noqa: E402
from parking.common.messaging import MqttBus  # noqa: E402
from parking.simulation import OccupancyTracker  # noqa: E402


def main() -> None:
    s = load_settings()
    bus = MqttBus(host=s.broker_host, port=s.broker_port, client_id="laptop")

    tracker = OccupancyTracker(bus)  # stand-in for storage + visualization

    def trace(topic: str, payload: bytes) -> None:
        env = json.loads(payload)
        print(f"[laptop] {topic:26} {env['type']:14} {env['data']}")

    bus.subscribe(topics.ALL, trace)

    bus.start()
    print(f"[laptop] connected to broker {s.broker_host}:{s.broker_port}; watching the bus. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        bus.stop()
        print(f"\n[laptop] final lot state: {tracker.occupied}")


if __name__ == "__main__":
    main()
