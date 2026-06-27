"""The dispatcher: turning a solved plan into ordered actuator commands.

`dispatching` is the control seam between AI planning and the hardware. It
consumes `PlanMessage`s from the planner and republishes them as the concrete
`GateCommand` / `BufferLedCommand` / `VehicleMoveCommand`s that the actuators
act on, in the right order.

(The *reactive* gate rule - open the gate on motion + a known card - is the
other half of control. Today it lives in `parking.simulation` as
`ReactiveGateController`; per docs/message-flow.md "Open decisions" it will move
here. Both styles are just bus `Component`s.)
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..common.component import Component
from ..common.models import PlanMessage


@runtime_checkable
class Dispatcher(Component, Protocol):
    """Consumes plans off the bus and drives the actuators to execute them."""

    def execute(self, plan: PlanMessage) -> None:
        """Translate one solved plan into ordered actuator commands."""
        ...
