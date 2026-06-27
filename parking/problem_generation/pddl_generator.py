"""PDDL problem generator (skeleton).

Reads the `StateStore` and renders a PDDL `(define (problem ...))` string that
targets the domain in `parking/planning/domain`. The string-building is the
`TODO`; the seam (state in -> `ProblemMessage` out) is fixed by
`ProblemGenerator`.
"""
from __future__ import annotations

from itertools import count

from ..common import models as m
from ..storage.base import StateStore
from .base import ProblemGenerator


class PddlProblemGenerator(ProblemGenerator):
    """Render the current state as a PDDL problem for the parking domain."""

    def __init__(self, domain_name: str = "parking") -> None:
        self._domain = domain_name
        self._ids = count(1)

    def generate(self, store: StateStore) -> m.ProblemMessage:
        problem_id = f"prob-{next(self._ids)}"
        # TODO: derive :objects (cars, spots, buffer), :init (free/occupied spots,
        #       vehicle<->spot, durations) and :goal (e.g. minimal walking
        #       distance) from `store`, then format the PDDL text.
        pddl = f"(define (problem {problem_id}) (:domain {self._domain}))"
        return m.ProblemMessage(problem_id=problem_id, pddl=pddl, source="problem_generation")
