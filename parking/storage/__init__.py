"""Persistent system state (Laptop).

    from parking.storage import StateStore              # the interface
    from parking.storage import InMemoryStore           # default implementation
    from parking.storage import Customer                # a stored record

`StateStore` is the storage surface (occupancy + customer DB + vehicle<->spot
mapping). Problem generation and visualization depend on the interface, never on
a concrete store, so the in-memory default swaps cleanly for a DB later.
`StorageService` is the `Component` that keeps a store current from bus events.
"""
from .base import (
    ARRIVAL_REQUESTED, DEPARTED, ENTRY_AUTHORIZED, EXIT_AUTHORIZED, IN_BUFFER,
    OUTSIDE, PARKED, PARKING, PICKUP_REQUESTED, READY_FOR_PICKUP, REJECTED,
    RETRIEVING, Customer, CustomerStore, OccupancyStore, StateStore,
)
from .memory_store import InMemoryStore
from .service import StorageService

__all__ = [
    "StateStore",
    "OccupancyStore",
    "CustomerStore",
    "Customer",
    "InMemoryStore",
    "StorageService",
    "ARRIVAL_REQUESTED", "ENTRY_AUTHORIZED", "IN_BUFFER", "PARKING", "PARKED",
    "PICKUP_REQUESTED", "RETRIEVING", "READY_FOR_PICKUP", "EXIT_AUTHORIZED",
    "DEPARTED", "REJECTED", "OUTSIDE",
]
