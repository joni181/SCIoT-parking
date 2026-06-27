"""The problem-generation contract.

Turns the current world state (read from a `StateStore`) into a PDDL
`ProblemMessage` for the planner. It pairs with the PDDL **domain** in
`parking/planning/domain`: the generator emits the `:objects`, `:init` and
`:goal` for that domain.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..common.models import ProblemMessage
from ..storage.base import StateStore


@runtime_checkable
class ProblemGenerator(Protocol):
    """Builds a PDDL problem instance from the current stored state."""

    def generate(self, store: StateStore) -> ProblemMessage:
        """Read ``store`` and return a `ProblemMessage` ready for the planner."""
        ...
