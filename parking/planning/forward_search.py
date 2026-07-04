"""Forward-search classical planner (skeleton).

Parses the PDDL `ProblemMessage` against the domain in `domain/` and runs a
forward state-space search to the goal, returning the action sequence as a
`PlanMessage`. The search itself is the `TODO`; the seam (problem in -> plan
out) is fixed by `Planner`.
"""
from __future__ import annotations

from ..common.models import PlanMessage, ProblemMessage
from .base import Planner


class ForwardSearchPlanner(Planner):
    """Solve the parking domain with forward state-space search."""

    def solve(self, problem: ProblemMessage) -> PlanMessage:
        # TODO: parse problem.pddl + the domain, run forward search to the goal,
        #       and turn the resulting action path into [{"name", "args"}, ...].
        actions: list = []
        return PlanMessage(problem_id=problem.problem_id, actions=actions, source="planning")
