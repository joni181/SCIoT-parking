"""Plan execution / dispatcher logic (Raspberry Pi).

    from parking.dispatching import Dispatcher          # the interface
    from parking.dispatching import PlanDispatcher      # plan executor (skeleton)

A `Dispatcher` consumes `PlanMessage`s and republishes them as ordered actuator
commands. The reactive gate rule lives (for now) in `parking.simulation` as
`ReactiveGateController` and will move here.
"""
from .base import Dispatcher
from .dispatcher import PlanDispatcher

__all__ = ["Dispatcher", "PlanDispatcher"]
