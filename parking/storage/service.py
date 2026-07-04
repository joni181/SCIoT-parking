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

    def __init__(
        self,
        bus: MessageBus,
        store: StateStore,
        source: str = "storage",
        buffer_id: str = "B1",
    ) -> None:
        self._bus = bus
        self._store = store
        self._source = source
        self._buffer_id = buffer_id
        self._latest_duration: int | None = None

    def start(self) -> None:
        self._bus.subscribe_message(m.OccupancyEvent.TOPIC, self._on_occupancy)
        self._bus.subscribe_message(m.NfcScanEvent.TOPIC, self._on_nfc)
        self._bus.subscribe_message(m.DurationDialEvent.TOPIC, self._on_duration)
        self._bus.subscribe_message(m.VehicleMoveCommand.TOPIC, self._on_vehicle_move)

    def stop(self) -> None:
        ...

    def _on_occupancy(self, msg: m.OccupancyEvent) -> None:
        self._store.set_occupancy(msg.spot_id, msg.occupied)

    def _on_nfc(self, msg: m.NfcScanEvent) -> None:
        customer = self._store.customer_for(msg.uid)
        if customer is None:
            customer = Customer(uid=msg.uid, vehicle_uid=msg.uid)

        if msg.reader == m.READER_GATE:
            customer.vehicle_uid = customer.vehicle_uid or msg.uid
            customer.expected_minutes = self._latest_duration
            customer.ready_for_pickup = False
            self._store.upsert_customer(customer)
            self._store.set_vehicle_spot(customer.vehicle_uid, self._buffer_id)
            self._store.set_occupancy(self._buffer_id, True)
            self._latest_duration = None
        elif msg.reader == m.READER_CHECKOUT:
            customer.ready_for_pickup = True
            self._store.upsert_customer(customer)

    def _on_duration(self, msg: m.DurationDialEvent) -> None:
        self._latest_duration = msg.minutes

    def _on_vehicle_move(self, msg: m.VehicleMoveCommand) -> None:
        """Apply commanded moves optimistically until sensors confirm them."""
        self._store.set_occupancy(msg.from_spot, False)
        self._store.set_occupancy(msg.to_spot, True)
        self._store.set_vehicle_spot(msg.vehicle_uid, msg.to_spot)
