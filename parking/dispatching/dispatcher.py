"""Plan-executing dispatcher.

Subscribes to `PlanMessage`s (in `start()`) and, for each, walks the ordered
`actions` and emits the matching actuator command. The action vocabulary is
defined by the PDDL domain in `parking/planning/domain`; mapping each action
name to its corresponding vehicle-move command.
"""
from __future__ import annotations

from ..common import models as m
from ..common.messaging import MessageBus
from .base import Dispatcher


class PlanDispatcher(Dispatcher):
    """Execute solved plans by issuing actuator commands in order."""

    def __init__(self, bus: MessageBus, source: str = "dispatcher") -> None:
        self._bus = bus
        self._source = source

    def start(self) -> None:
        self._bus.subscribe_message(m.PlanMessage.TOPIC, self.execute)

    def stop(self) -> None:
        ...

    def execute(self, plan: m.PlanMessage) -> None:
        for action in plan.actions:
            self._dispatch(action)

    def _dispatch(self, action: dict) -> None:
        name = action.get("name")
        args = action.get("args", [])
        if name == "park" and len(args) == 3:
            car, buffer, spot = args
            command = m.VehicleMoveCommand(
                vehicle_uid=car,
                from_spot=buffer,
                to_spot=spot,
                source=self._source,
            )
        elif name == "retrieve" and len(args) == 3:
            car, spot, buffer = args
            command = m.VehicleMoveCommand(
                vehicle_uid=car,
                from_spot=spot,
                to_spot=buffer,
                source=self._source,
            )
        else:
            raise ValueError(f"unsupported or malformed planner action: {action!r}")
        self._bus.publish_message(command)
