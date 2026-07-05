"""Dependency-free typed STRIPS parser and breadth-first forward planner."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from ..common.models import PlanMessage, ProblemMessage
from .base import Planner

Atom = tuple[str, ...]
SExpr = str | list["SExpr"]


class PlanningError(ValueError):
    """Raised when PDDL is unsupported, invalid, or has no solution."""


@dataclass(frozen=True)
class Literal:
    atom: Atom
    positive: bool = True


@dataclass(frozen=True)
class ActionSchema:
    name: str
    parameters: tuple[tuple[str, str], ...]
    preconditions: tuple[Literal, ...]
    effects: tuple[Literal, ...]


@dataclass(frozen=True)
class GroundAction:
    name: str
    args: tuple[str, ...]
    positive_preconditions: frozenset[Atom]
    negative_preconditions: frozenset[Atom]
    add_effects: frozenset[Atom]
    delete_effects: frozenset[Atom]

    def applicable(self, state: frozenset[Atom]) -> bool:
        return self.positive_preconditions <= state and not (self.negative_preconditions & state)

    def apply(self, state: frozenset[Atom]) -> frozenset[Atom]:
        return (state - self.delete_effects) | self.add_effects


@dataclass(frozen=True)
class ParsedProblem:
    objects: dict[str, tuple[str, ...]]
    initial: frozenset[Atom]
    goals: tuple[Literal, ...]


class ForwardSearchPlanner(Planner):
    """Solve typed STRIPS problems with complete breadth-first search."""

    def __init__(self, domain_path: str | Path | None = None, max_states: int = 100_000) -> None:
        self._domain_path = Path(domain_path) if domain_path else Path(__file__).with_name("domain") / "domain.pddl"
        self._max_states = max_states

    def solve(self, problem: ProblemMessage) -> PlanMessage:
        domain = _parse_domain(self._domain_path.read_text(encoding="utf-8"))
        parsed = _parse_problem(problem.pddl)
        grounded = tuple(_ground_actions(domain, parsed.objects))
        path = self._search(parsed.initial, parsed.goals, grounded)
        actions = [{"name": action.name, "args": list(action.args)} for action in path]
        return PlanMessage(problem_id=problem.problem_id, actions=actions, source="planning")

    def _search(
        self,
        initial: frozenset[Atom],
        goals: Sequence[Literal],
        actions: Sequence[GroundAction],
    ) -> list[GroundAction]:
        if _goal_reached(initial, goals):
            return []

        queue = deque([(initial, [])])
        visited = {initial}
        while queue:
            state, path = queue.popleft()
            for action in actions:
                if not action.applicable(state):
                    continue
                successor = action.apply(state)
                if successor in visited:
                    continue
                next_path = [*path, action]
                if _goal_reached(successor, goals):
                    return next_path
                visited.add(successor)
                if len(visited) > self._max_states:
                    raise PlanningError(f"search exceeded limit of {self._max_states} states")
                queue.append((successor, next_path))
        raise PlanningError("problem has no solution")


def _tokenize(text: str) -> list[str]:
    text = re.sub(r";[^\r\n]*", "", text)
    return re.findall(r"\(|\)|[^\s()]+", text)


def _parse_sexpr(text: str) -> list[SExpr]:
    tokens = iter(_tokenize(text))

    def parse_list() -> list[SExpr]:
        result: list[SExpr] = []
        for token in tokens:
            if token == "(":
                result.append(parse_list())
            elif token == ")":
                return result
            else:
                result.append(token)
        raise PlanningError("unclosed PDDL expression")

    try:
        if next(tokens) != "(":
            raise PlanningError("PDDL document must start with '('")
    except StopIteration as exc:
        raise PlanningError("empty PDDL document") from exc
    root = parse_list()
    try:
        next(tokens)
    except StopIteration:
        return root
    raise PlanningError("extra tokens after PDDL document")


def _sections(root: list[SExpr]) -> Iterator[list[SExpr]]:
    if not root or str(root[0]).lower() != "define":
        raise PlanningError("expected a PDDL define form")
    for item in root[1:]:
        if isinstance(item, list) and item:
            yield item


def _parse_domain(text: str) -> tuple[ActionSchema, ...]:
    actions: list[ActionSchema] = []
    for section in _sections(_parse_sexpr(text)):
        if str(section[0]).lower() != ":action":
            continue
        if len(section) < 2 or not isinstance(section[1], str):
            raise PlanningError("action is missing its name")
        fields = _keyword_fields(section[2:])
        parameters_expr = fields.get(":parameters", [])
        if not isinstance(parameters_expr, list):
            raise PlanningError("action parameters must be a list")
        actions.append(
            ActionSchema(
                name=section[1],
                parameters=tuple(_typed_names(parameters_expr)),
                preconditions=tuple(_literals(fields.get(":precondition", ["and"]))),
                effects=tuple(_literals(fields.get(":effect", ["and"]))),
            )
        )
    if not actions:
        raise PlanningError("domain contains no actions")
    return tuple(actions)


def _parse_problem(text: str) -> ParsedProblem:
    objects: dict[str, list[str]] = {}
    initial: set[Atom] = set()
    goals: tuple[Literal, ...] = ()
    for section in _sections(_parse_sexpr(text)):
        keyword = str(section[0]).lower()
        if keyword == ":objects":
            for name, type_name in _typed_names(section[1:]):
                objects.setdefault(type_name, []).append(name)
        elif keyword == ":init":
            for literal in _literals(["and", *section[1:]]):
                if not literal.positive:
                    raise PlanningError("negative initial facts are not supported")
                initial.add(literal.atom)
        elif keyword == ":goal":
            if len(section) != 2:
                raise PlanningError("goal must contain one expression")
            goals = tuple(_literals(section[1]))
    return ParsedProblem(
        objects={name: tuple(values) for name, values in objects.items()},
        initial=frozenset(initial),
        goals=goals,
    )


def _keyword_fields(items: Sequence[SExpr]) -> dict[str, SExpr]:
    result: dict[str, SExpr] = {}
    index = 0
    while index < len(items):
        key = items[index]
        if not isinstance(key, str) or not key.startswith(":") or index + 1 >= len(items):
            raise PlanningError("malformed action field")
        result[key.lower()] = items[index + 1]
        index += 2
    return result


def _typed_names(items: Sequence[SExpr]) -> list[tuple[str, str]]:
    if any(not isinstance(item, str) for item in items):
        raise PlanningError("typed name list cannot contain expressions")
    result: list[tuple[str, str]] = []
    pending: list[str] = []
    index = 0
    values = [str(item) for item in items]
    while index < len(values):
        if values[index] == "-":
            if not pending or index + 1 >= len(values):
                raise PlanningError("malformed typed name list")
            type_name = values[index + 1]
            result.extend((name, type_name) for name in pending)
            pending.clear()
            index += 2
        else:
            pending.append(values[index])
            index += 1
    result.extend((name, "object") for name in pending)
    return result


def _literals(expression: SExpr) -> list[Literal]:
    if not isinstance(expression, list) or not expression:
        raise PlanningError("expected a predicate expression")
    head = str(expression[0]).lower()
    if head == "and":
        result: list[Literal] = []
        for child in expression[1:]:
            result.extend(_literals(child))
        return result
    if head == "not":
        if len(expression) != 2:
            raise PlanningError("not must contain one predicate")
        literals = _literals(expression[1])
        if len(literals) != 1:
            raise PlanningError("not must contain one predicate")
        literal = literals[0]
        return [Literal(literal.atom, not literal.positive)]
    if any(not isinstance(value, str) for value in expression):
        raise PlanningError("nested terms are not supported")
    return [Literal(tuple(str(value) for value in expression))]


def _ground_actions(
    schemas: Iterable[ActionSchema], objects: dict[str, tuple[str, ...]]
) -> Iterator[GroundAction]:
    for schema in schemas:
        choices = [objects.get(type_name, ()) for _, type_name in schema.parameters]
        for args in product(*choices):
            bindings = {variable: value for (variable, _), value in zip(schema.parameters, args)}
            preconditions = [_ground_literal(item, bindings) for item in schema.preconditions]
            effects = [_ground_literal(item, bindings) for item in schema.effects]
            yield GroundAction(
                name=schema.name,
                args=tuple(args),
                positive_preconditions=frozenset(x.atom for x in preconditions if x.positive),
                negative_preconditions=frozenset(x.atom for x in preconditions if not x.positive),
                add_effects=frozenset(x.atom for x in effects if x.positive),
                delete_effects=frozenset(x.atom for x in effects if not x.positive),
            )


def _ground_literal(literal: Literal, bindings: dict[str, str]) -> Literal:
    return Literal(tuple(bindings.get(value, value) for value in literal.atom), literal.positive)


def _goal_reached(state: frozenset[Atom], goals: Sequence[Literal]) -> bool:
    return all((goal.atom in state) == goal.positive for goal in goals)
