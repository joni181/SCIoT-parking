"""Generate concrete parking problems for the PDDL domain."""
from __future__ import annotations

import re
from itertools import count
from typing import Iterable, Sequence

from ..common import models as m
from ..storage.base import Customer, StateStore
from .base import ProblemGenerator

_PDDL_SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _symbol(value: str) -> str:
    """Validate identifiers before embedding them in a PDDL document."""
    if not _PDDL_SYMBOL.fullmatch(value):
        raise ValueError(f"not a valid PDDL identifier: {value!r}")
    return value


class PddlProblemGenerator(ProblemGenerator):
    """Render current storage state as a solvable parking problem.

    Spots are ordered nearest-to-entrance first. Cars with the shortest expected
    stay receive the nearest available spots, reducing expected retrieval
    latency without requiring numeric PDDL extensions.
    """

    def __init__(
        self,
        domain_name: str = "parking",
        spots: Sequence[str] = ("P1", "P2", "P3"),
        buffers: Sequence[str] = ("B1",),
    ) -> None:
        if not spots or not buffers:
            raise ValueError("at least one parking spot and buffer are required")
        self._domain = _symbol(domain_name)
        self._spots = tuple(_symbol(item) for item in spots)
        self._buffers = tuple(_symbol(item) for item in buffers)
        self._ids = count(1)

    def generate(self, store: StateStore) -> m.ProblemMessage:
        problem_id = f"prob-{next(self._ids)}"
        locations = store.vehicle_locations()
        customers = [c for c in store.customers() if c.vehicle_uid and c.vehicle_uid in locations]
        cars = sorted({_symbol(c.vehicle_uid) for c in customers})

        occupied_by_vehicle = set(locations.values())
        free_spots = [
            spot for spot in self._spots
            if spot not in occupied_by_vehicle and not store.is_occupied(spot)
        ]
        free_buffers = [
            buffer for buffer in self._buffers
            if buffer not in occupied_by_vehicle and not store.is_occupied(buffer)
        ]

        init: list[str] = []
        for spot in free_spots:
            init.append(f"(free-spot {spot})")
        for buffer in free_buffers:
            init.append(f"(free-buffer {buffer})")
        for car in cars:
            location = _symbol(locations[car])
            if location in self._spots:
                init.append(f"(at {car} {location})")
            elif location in self._buffers:
                init.append(f"(in-buffer {car} {location})")
            else:
                raise ValueError(f"unknown location {location!r} for vehicle {car!r}")

        goals = self._goals(customers, locations, free_spots)
        objects = self._typed_objects(cars, "car")
        objects += self._typed_objects(self._spots, "spot")
        objects += self._typed_objects(self._buffers, "buffer")
        objects_text = "\n    ".join(objects)
        init_text = "\n      ".join(init)
        goal_text = "\n        ".join(goals)
        pddl = (
            f"(define (problem {problem_id})\n"
            f"  (:domain {self._domain})\n"
            f"  (:objects\n    {objects_text}\n  )\n"
            f"  (:init\n      {init_text}\n  )\n"
            f"  (:goal (and\n        {goal_text}\n  ))\n"
            f")"
        )
        return m.ProblemMessage(problem_id=problem_id, pddl=pddl, source="problem_generation")

    def _goals(
        self,
        customers: Iterable[Customer],
        locations: dict[str, str],
        free_spots: list[str],
    ) -> list[str]:
        goals: list[str] = []

        # Checkout requests have priority. A free buffer may be created by first
        # parking an arriving car, so retrieval remains a normal search problem.
        for customer in sorted(customers, key=lambda item: item.vehicle_uid):
            car = _symbol(customer.vehicle_uid)
            if customer.ready_for_pickup and locations[customer.vehicle_uid] in self._spots:
                goals.append(f"(in-buffer {car} {self._buffers[0]})")

        arrivals = [
            customer for customer in customers
            if not customer.ready_for_pickup and locations[customer.vehicle_uid] in self._buffers
        ]
        arrivals.sort(
            key=lambda item: (
                item.expected_minutes if item.expected_minutes is not None else float("inf"),
                item.vehicle_uid,
            )
        )
        for customer, spot in zip(arrivals, free_spots):
            goals.append(f"(at {_symbol(customer.vehicle_uid)} {spot})")
        return goals

    @staticmethod
    def _typed_objects(values: Iterable[str], type_name: str) -> list[str]:
        values = list(values)
        return [f"{' '.join(values)} - {type_name}"] if values else []
