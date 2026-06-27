"""Plan-executing dispatcher (skeleton).

Subscribes to `PlanMessage`s (in `start()`) and, for each, walks the ordered
`actions` and emits the matching actuator command. The action vocabulary is
defined by the PDDL domain in `parking/planning/domain`; mapping each action
name to a command is the `TODO` below.
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
        # TODO: map an action {"name": ..., "args": [...]} to a command, e.g.
        #   "park"     -> VehicleMoveCommand(from_spot=buffer, to_spot=spot)
        #   "retrieve" -> VehicleMoveCommand(from_spot=spot, to_spot=buffer)
        #   "open_gate"-> GateCommand(action=m.GATE_OPEN)
        # then self._bus.publish_message(cmd).
        ...
