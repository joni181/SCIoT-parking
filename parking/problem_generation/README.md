# problem_generation  [laptop]

Translates current occupancy, vehicle locations, pickup requests, and expected
durations into a PDDL problem for `parking/planning`.

**Interface:** [`ProblemGenerator`](base.py) - `generate(store) -> ProblemMessage`.
[`pddl_generator.py`](pddl_generator.py) emits typed objects, current/free
locations, and concrete assignment/retrieval goals. Configured spots are ordered
by distance to the entrance; shorter expected stays receive nearer free spots.
[`service.py`](service.py) regenerates a problem after relevant state events.
