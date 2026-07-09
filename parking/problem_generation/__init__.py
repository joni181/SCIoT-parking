"""Build PDDL problems from current state (Laptop).

    from parking.problem_generation import ProblemGenerator      # the interface
    from parking.problem_generation import PddlProblemGenerator

A `ProblemGenerator` reads a `parking.storage.StateStore` and emits a
`ProblemMessage` for the planner, targeting the domain in
`parking/planning/domain`.
"""
from .base import ProblemGenerator
from .pddl_generator import PddlProblemGenerator
from .service import ProblemGenerationService

__all__ = ["ProblemGenerator", "PddlProblemGenerator", "ProblemGenerationService"]
