"""Keep a `StateStore` in sync with the bus.

`InMemoryStore` is passive data; this `Component` is the wire that feeds it. It
subscribes to the events that change durable state and applies them, so the
laptop's storage stays current as the Pi reports the world. Visualization and
problem generation then just *read* the store - they never touch the bus
plumbing here.
"""
from __future__ import annotations

from ..common import models as m
from ..common.messaging import MessageBus
from .base import Customer, StateStore


class StorageService:
    """Bus adapter that updates a `StateStore` from incoming events."""

    def __init__(self, bus: MessageBus, store: StateStore, source: str = "storage") -> None:
        self._bus = bus
        self._store = store
        self._source = source

    def start(self) -> None:
        self._bus.subscribe_message(m.OccupancyEvent.TOPIC, self._on_occupancy)
        self._bus.subscribe_message(m.NfcScanEvent.TOPIC, self._on_nfc)

    def stop(self) -> None:
        ...

    def _on_occupancy(self, msg: m.OccupancyEvent) -> None:
        self._store.set_occupancy(msg.spot_id, msg.occupied)

    def _on_nfc(self, msg: m.NfcScanEvent) -> None:
        # A gate scan means this customer is on site; register them if new.
        if msg.reader == m.READER_GATE and self._store.customer_for(msg.uid) is None:
            self._store.upsert_customer(Customer(uid=msg.uid))
        # TODO: pair DurationDialEvent + VehicleMoveCommand to fill in
        #       expected_minutes and the vehicle <-> spot mapping.
