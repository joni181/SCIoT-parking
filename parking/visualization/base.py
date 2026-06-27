"""The visualization contract.

A `View` is a read-only window on the system. It subscribes to the bus
(occupancy events, plans) and/or reads a `StateStore`, then renders: the
parking-lot occupancy display, the customer <-> vehicle map, the plan-execution
view. Crucially it has **no path back to control logic** - it only observes, so
it can never affect what the system does.

A view is a `Component` (it `start()`s its subscriptions / window and `stop()`s
them) plus a `render()` to (re)draw on demand.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..common.component import Component


@runtime_checkable
class View(Component, Protocol):
    """A read-only renderer of system state."""

    def render(self) -> None:
        """Draw the current state once (views may also redraw on bus events)."""
        ...
