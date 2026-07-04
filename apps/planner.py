"""Standalone planner service (runs on either node).

Subscribes to generated PDDL problems, solves each with forward search, and
publishes the resulting plan for the dispatcher.

    python apps/planner.py
    PARKING_BROKER_HOST=192.168.0.10 python apps/planner.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parking.common import load_settings  # noqa: E402
from parking.common.messaging import MqttBus  # noqa: E402
from parking.planning import ForwardSearchPlanner, PlannerService  # noqa: E402


def main() -> None:
    s = load_settings()
    bus = MqttBus(host=s.broker_host, port=s.broker_port, client_id="planner")
    service = PlannerService(bus, ForwardSearchPlanner())
    service.start()

    bus.start()
    print(f"[planner] connected to broker {s.broker_host}:{s.broker_port}; waiting for problems. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        bus.stop()


if __name__ == "__main__":
    main()
