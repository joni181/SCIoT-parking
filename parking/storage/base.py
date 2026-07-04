"""The storage contract: the system's memory, behind one interface.

`storage` holds the durable state everyone else reads: which vehicle is in which
spot, and the customer DB (card UID <-> customer, expected parking duration).
Problem generation and visualization depend on *these methods*, never on a
concrete database - so an in-memory dict today and a real DB later are a drop-in
swap.

Three Protocols, smallest first, so a consumer can ask for exactly the slice it
needs:

  * `OccupancyStore` - who is parked where (updated from `OccupancyEvent`s).
  * `CustomerStore`  - the customer / vehicle / duration records.
  * `StateStore`     - both together: the full storage surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol, runtime_checkable


@dataclass
class Customer:
    """One registered customer, keyed by their NFC card UID."""

    uid: str
    vehicle_uid: str = ""
    expected_minutes: Optional[int] = None
    ready_for_pickup: bool = False


@runtime_checkable
class OccupancyStore(Protocol):
    """Which spots are taken. Fed by occupancy events, read by planning/viz."""

    def is_occupied(self, spot_id: str) -> bool: ...

    def set_occupancy(self, spot_id: str, occupied: bool) -> None: ...

    def free_spots(self, spots: Iterable[str]) -> List[str]:
        """Of ``spots``, those currently free."""
        ...


@runtime_checkable
class CustomerStore(Protocol):
    """The customer DB and the vehicle <-> spot mapping."""

    def upsert_customer(self, customer: Customer) -> None: ...

    def customer_for(self, uid: str) -> Optional[Customer]: ...

    def set_vehicle_spot(self, vehicle_uid: str, spot_id: str) -> None: ...

    def spot_of_vehicle(self, vehicle_uid: str) -> Optional[str]: ...

    def customers(self) -> List[Customer]:
        """Return a stable snapshot of all registered customers."""
        ...

    def vehicle_locations(self) -> dict[str, str]:
        """Return a snapshot of the vehicle-to-location mapping."""
        ...


@runtime_checkable
class StateStore(OccupancyStore, CustomerStore, Protocol):
    """The complete storage surface: occupancy + customers + mapping."""
