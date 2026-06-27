"""Persistent system state (Laptop).

    from parking.storage import StateStore              # the interface
    from parking.storage import InMemoryStore           # default implementation
    from parking.storage import Customer                # a stored record

`StateStore` is the storage surface (occupancy + customer DB + vehicle<->spot
mapping). Problem generation and visualization depend on the interface, never on
a concrete store, so the in-memory default swaps cleanly for a DB later.
"""
from .base import Customer, CustomerStore, OccupancyStore, StateStore
from .memory_store import InMemoryStore

__all__ = ["StateStore", "OccupancyStore", "CustomerStore", "Customer", "InMemoryStore"]
