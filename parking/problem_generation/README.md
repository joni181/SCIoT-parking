# problem_generation  [laptop]

Translates the current world state (occupancy + customer durations from `storage`)
into a PDDL **problem** for the planner. Pairs with the PDDL **domain** in `planning/`.

**Interface:** [`ProblemGenerator`](base.py) — `generate(store) -> ProblemMessage`.
Skeleton implementation in [`pddl_generator.py`](pddl_generator.py).
