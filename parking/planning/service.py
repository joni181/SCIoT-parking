"""Bus-facing planner service."""
from __future__ import annotations

from ..common import models as m
from ..common.messaging import MessageBus
from .base import Planner
from .forward_search import PlanningError


class PlannerService:
    def __init__(self, bus: MessageBus, planner: Planner) -> None:
        self._bus = bus
        self._planner = planner
        self.last_error: PlanningError | None = None

    def start(self) -> None:
        self._bus.subscribe_message(m.ProblemMessage.TOPIC, self._on_problem)

    def stop(self) -> None:
        ...

    def _on_problem(self, problem: m.ProblemMessage) -> None:
        try:
            plan = self._planner.solve(problem)
        except PlanningError as exc:
            # State changes can temporarily be unsatisfiable (for example, all
            # spots and the buffer are occupied). Keep the service alive; the
            # next state event will generate and solve a fresh problem.
            self.last_error = exc
            return
        self.last_error = None
        self._bus.publish_message(plan)
