"""Generate one safe, sensor-bounded planning phase from the live state."""
from __future__ import annotations

import re
from itertools import count
from typing import Sequence

from ..common import models as m
from ..storage.base import (
    ARRIVAL_REQUESTED,
    ENTRY_AUTHORIZED,
    EXIT_AUTHORIZED,
    IN_BUFFER,
    OUTSIDE,
    PARKED,
    PICKUP_REQUESTED,
    READY_FOR_PICKUP,
    RETRIEVING,
    Customer,
    StateStore,
)
from .base import ProblemGenerator

_PDDL_SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _symbol(value: str) -> str:
    if not _PDDL_SYMBOL.fullmatch(value):
        raise ValueError(f"not a valid PDDL identifier: {value!r}")
    return value


class PddlProblemGenerator(ProblemGenerator):
    """Prioritize the resource owner, then queued pickup, then arrival requests."""

    def __init__(
        self,
        domain_name: str = "parking",
        spots: Sequence[str] = ("P1", "P2", "P3"),
        buffers: Sequence[str] = ("B1",),
    ) -> None:
        if not spots or not buffers:
            raise ValueError("at least one parking spot and buffer are required")
        self._domain = _symbol(domain_name)
        self._spots = tuple(_symbol(x) for x in spots)
        self._buffers = tuple(_symbol(x) for x in buffers)
        self._ids = count(1)

    def generate(self, store: StateStore) -> m.ProblemMessage:
        problem_id = f"prob-{next(self._ids)}"
        customers = [c for c in store.customers() if c.vehicle_uid]
        target, purpose = self._select_request(customers)
        cars = sorted({_symbol(c.vehicle_uid) for c in customers})
        locations = store.vehicle_locations()

        reserved_spots = {
            c.assigned_spot for c in customers
            if c.assigned_spot and c.status not in (PARKED, EXIT_AUTHORIZED)
        }
        reserved_buffers = {
            c.assigned_buffer for c in customers
            if c.assigned_buffer and c.status in (ENTRY_AUTHORIZED, IN_BUFFER, RETRIEVING, READY_FOR_PICKUP, EXIT_AUTHORIZED)
        }
        free_spots = [s for s in self._spots if not store.is_occupied(s) and s not in reserved_spots]
        free_buffers = [b for b in self._buffers if not store.is_occupied(b) and b not in reserved_buffers]

        init: list[str] = [*(f"(free-spot {s})" for s in free_spots), *(f"(free-buffer {b})" for b in free_buffers)]
        for customer in customers:
            car = _symbol(customer.vehicle_uid)
            location = locations.get(customer.vehicle_uid)
            if location == OUTSIDE:
                init.append(f"(outside {car})")
            elif location in self._spots:
                init.append(f"(at {car} {location})")
            elif location in self._buffers:
                init.append(f"(in-buffer {car} {location})")
            if customer.status == ARRIVAL_REQUESTED:
                init.append(f"(arrival-requested {car})")
            if customer.checkout_requested or customer.status == PICKUP_REQUESTED:
                init.append(f"(pickup-requested {car})")
            if customer.assigned_spot:
                init.append(f"(assigned {car} {customer.assigned_spot})")
            if customer.status in (READY_FOR_PICKUP, EXIT_AUTHORIZED) and customer.assigned_buffer:
                init.append(f"(ready-for-pickup {car} {customer.assigned_buffer})")

        goals: list[str] = []
        request_uid = target.vehicle_uid if target else ""
        if target is not None:
            car = _symbol(target.vehicle_uid)
            if purpose == "arrival":
                spot = self._preferred_spot(target, free_spots)
                buffer = free_buffers[0] if free_buffers else self._buffers[0]
                goals.append(f"(assignment-shown {car} {spot})")
            elif purpose == "park":
                goals.append(f"(at {car} {target.assigned_spot})")
            elif purpose == "retrieve":
                buffer = free_buffers[0] if free_buffers else self._buffers[0]
                goals.append(f"(ready-for-pickup {car} {buffer})")
            elif purpose == "exit":
                goals.append(f"(exit-authorized {car} {target.assigned_buffer})")

        object_lines = []
        if cars:
            object_lines.append(f"{' '.join(cars)} - car")
        object_lines.append(f"{' '.join(self._spots)} - spot")
        object_lines.append(f"{' '.join(self._buffers)} - buffer")
        objects_text = "\n    ".join(object_lines)
        init_text = "\n    ".join(init)
        goals_text = "\n    ".join(goals)
        pddl = (
            f"(define (problem {problem_id})\n"
            f"  (:domain {self._domain})\n"
            f"  (:objects\n    {objects_text}\n  )\n"
            f"  (:init\n    {init_text}\n  )\n"
            f"  (:goal (and\n    {goals_text}\n  ))\n)"
        )
        return m.ProblemMessage(
            problem_id=problem_id,
            pddl=pddl,
            request_uid=request_uid,
            purpose=purpose,
            source="problem_generation",
        )

    def _preferred_spot(self, customer: Customer, free_spots: list[str]) -> str:
        if not free_spots:
            return self._spots[0]
        minutes = customer.expected_minutes or 0
        # Configuration is nearest-first. Each expected hour shifts the
        # assignment one position farther away, preserving close spots for
        # short visits while remaining deterministic and explainable.
        index = min(max(minutes // 60, 0), len(free_spots) - 1)
        return free_spots[index]

    @staticmethod
    def _select_request(customers: list[Customer]) -> tuple[Customer | None, str]:
        def oldest(statuses: tuple[str, ...]) -> Customer | None:
            matches = [c for c in customers if c.status in statuses]
            return min(matches, key=lambda c: c.requested_at) if matches else None

        target = oldest((READY_FOR_PICKUP,))
        if target:
            return target, "exit"
        target = oldest((IN_BUFFER,))
        if target:
            return target, "exit" if target.checkout_requested else "park"
        target = oldest((PICKUP_REQUESTED, PARKED))
        if target and target.checkout_requested:
            return target, "retrieve"
        target = oldest((ARRIVAL_REQUESTED,))
        if target:
            return target, "arrival"
        return None, ""
