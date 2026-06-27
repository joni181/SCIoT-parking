"""The planner contract: one method, problem in -> plan out.

The classical-planning seam. `solve` takes the `ProblemMessage` from problem
generation and returns a `PlanMessage` for the dispatcher. Keeping the surface
this small means the forward-search planner here can be swapped for any other
solver - or an external planner process - without touching the rest of the
system.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..common.models import PlanMessage, ProblemMessage


@runtime_checkable
class Planner(Protocol):
    """Solves a PDDL problem into an ordered plan."""

    def solve(self, problem: ProblemMessage) -> PlanMessage:
        """Return a `PlanMessage` whose ``actions`` solve ``problem``."""
        ...
