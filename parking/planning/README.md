# planning  [either node]

Classical planning with typed STRIPS and breadth-first forward search. The PDDL
domain in `domain/` defines parking and retrieval actions. The planner parses and
solves each runtime problem, then publishes the shortest action sequence for the
dispatcher.

**Interface:** [`Planner`](base.py) - `solve(problem) -> PlanMessage`.
[`forward_search.py`](forward_search.py) supports typed objects, positive/negative
STRIPS preconditions and effects, conjunctive goals, action grounding, and bounded
BFS. [`service.py`](service.py) connects it to problem and plan topics.
