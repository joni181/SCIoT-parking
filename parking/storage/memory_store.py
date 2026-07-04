"""In-memory `StateStore` - the default, dependency-free implementation.

Plain dicts behind the `StateStore` interface: enough to run, test and demo the
whole system today. Swapping it for a file- or DB-backed store later means
writing another `StateStore` and changing one line where the store is
constructed - nothing else moves.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .base import Customer, StateStore


class InMemoryStore(StateStore):
    """A `StateStore` kept entirely in process memory."""

    def __init__(self) -> None:
        self._occupied: Dict[str, bool] = {}
        self._customers: Dict[str, Customer] = {}      # uid -> Customer
        self._vehicle_spot: Dict[str, str] = {}        # vehicle_uid -> spot_id

    # --- OccupancyStore ----------------------------------------------------
    def is_occupied(self, spot_id: str) -> bool:
        return self._occupied.get(spot_id, False)

    def set_occupancy(self, spot_id: str, occupied: bool) -> None:
        self._occupied[spot_id] = occupied

    def free_spots(self, spots: Iterable[str]) -> List[str]:
        return [s for s in spots if not self._occupied.get(s, False)]

    # --- CustomerStore -----------------------------------------------------
    def upsert_customer(self, customer: Customer) -> None:
        self._customers[customer.uid] = customer

    def customer_for(self, uid: str) -> Optional[Customer]:
        return self._customers.get(uid)

    def set_vehicle_spot(self, vehicle_uid: str, spot_id: str) -> None:
        self._vehicle_spot[vehicle_uid] = spot_id

    def spot_of_vehicle(self, vehicle_uid: str) -> Optional[str]:
        return self._vehicle_spot.get(vehicle_uid)

    def customers(self) -> List[Customer]:
        return list(self._customers.values())

    def vehicle_locations(self) -> Dict[str, str]:
        return dict(self._vehicle_spot)

    # --- convenience (impl-only, not part of the StateStore interface) -----
    def occupied_spots(self) -> List[str]:
        """The spots currently marked occupied (handy for logging / a dump)."""
        return sorted(spot for spot, occ in self._occupied.items() if occ)

    # TODO: persist to disk / a real DB so state survives a restart.
