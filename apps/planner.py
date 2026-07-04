"""Standalone planner service (runs on either node).

Subscribes to generated PDDL problems, solves each with the forward-search
`Planner`, and publishes the resulting `PlanMessage` for the dispatcher. The current
planner is a skeleton that returns an empty placeholder plan. The service stays idle
until `problem_generation` starts publishing problems; the control loop that triggers
planning is also still pending (see docs/message-flow.md).

    python apps/planner.py
    PARKING_BROKER_HOST=192.168.0.10 python apps/planner.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parking.common import load_settings  # noqa: E402
from parking.common import models as m  # noqa: E402
from parking.common.messaging import MqttBus  # noqa: E402
from parking.planning import ForwardSearchPlanner  # noqa: E402


def main() -> None:
    s = load_settings()
    bus = MqttBus(host=s.broker_host, port=s.broker_port, client_id="planner")
    planner = ForwardSearchPlanner()

    def on_problem(problem: m.ProblemMessage) -> None:
        plan = planner.solve(problem)
        bus.publish_message(plan)
        print(f"[planner] produced {len(plan.actions)} placeholder action(s) for {problem.problem_id}")

    bus.subscribe_message(m.ProblemMessage.TOPIC, on_problem)

    bus.start()
    print(f"[planner] connected to broker {s.broker_host}:{s.broker_port}; waiting for problems. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        bus.stop()


if __name__ == "__main__":
    main()
