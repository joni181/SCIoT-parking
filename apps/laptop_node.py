"""Laptop node: the compute + UI side (storage, planner, visualization).

Composition root for storage, problem generation, forward planning and the UI.

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
from parking.planning import ForwardSearchPlanner, PlannerService  # noqa: E402
from parking.problem_generation import PddlProblemGenerator, ProblemGenerationService  # noqa: E402
from parking.storage import InMemoryStore, StorageService  # noqa: E402
from parking.visualization import DashboardModel, DashboardView  # noqa: E402


def main() -> None:
    s = load_settings()
    bus = MqttBus(host=s.broker_host, port=s.broker_port, client_id="laptop")

    store = InMemoryStore()
    planner = PlannerService(bus, ForwardSearchPlanner())
    generator = PddlProblemGenerator(spots=s.parking_spots, buffers=s.buffer_spots)
    problem_generation = ProblemGenerationService(bus, store, generator)
    dashboard_model = DashboardModel(bus, store, s.parking_spots, s.buffer_spots)
    dashboard = DashboardView(
        dashboard_model,
        host=s.dashboard_host,
        port=s.dashboard_port,
        open_browser=s.dashboard_open_browser,
    )
    bus_components = [
        StorageService(bus, store),  # keep the store current from bus events
        planner,                     # solve every generated problem
        problem_generation,          # regenerate after stored state changes
    ]

    def trace(topic: str, payload: bytes) -> None:
        env = json.loads(payload)
        print(f"[laptop] {topic:26} {env['type']:14} {env['data']}")

    bus.subscribe(topics.ALL, trace)
    for c in bus_components:
        c.start()
    try:
        bus.start()
    except OSError as exc:
        for c in reversed(bus_components):
            c.stop()
        print(
            "[laptop] could not connect to MQTT broker "
            f"{s.broker_host}:{s.broker_port}: {exc}\n"
            "[laptop] start the broker first with: python deploy/broker.py\n"
            "[laptop] no Raspberry Pi is required, but the broker process is.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    dashboard.start()
    print(
        f"[laptop] connected to broker {s.broker_host}:{s.broker_port}; "
        f"dashboard: {dashboard.url}. Ctrl-C to stop."
    )
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        dashboard.stop()
        for c in reversed(bus_components):
            c.stop()
        bus.stop()
        print(f"\n[laptop] final occupied spots (from storage): {store.occupied_spots()}")


if __name__ == "__main__":
    main()
