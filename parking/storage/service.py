"""Maintain planning-relevant lifecycle state from bus events and commands."""
from __future__ import annotations

from ..common import models as m
from ..common.messaging import MessageBus
from .base import (
    ARRIVAL_REQUESTED,
    DEPARTED,
    ENTRY_AUTHORIZED,
    EXIT_AUTHORIZED,
    IN_BUFFER,
    OUTSIDE,
    PARKED,
    PARKING,
    PICKUP_REQUESTED,
    READY_FOR_PICKUP,
    REJECTED,
    RETRIEVING,
    Customer,
    StateStore,
)


def _vehicle_uid_for(card_uid: str) -> str:
    """A vehicle identifier that's always a valid PDDL symbol.

    RFID card UIDs are raw hex, so they start with a digit as often as not,
    but `_symbol` in `pddl_generator.py` requires a leading letter. Prefix
    only when needed, so already-valid IDs (as used throughout the tests)
    round-trip unchanged.
    """
    return card_uid if card_uid[:1].isalpha() else f"v{card_uid}"


class StorageService:
    """Convert raw observations and planner commands into vehicle lifecycles."""

    def __init__(self, bus: MessageBus, store: StateStore, source: str = "storage") -> None:
        self._bus = bus
        self._store = store
        self._source = source
        self._latest_duration: int | None = None
        self._pending_moves: dict[str, m.VehicleMoveCommand] = {}
        self._gate_present = False

    def start(self) -> None:
        self._bus.subscribe_message(m.OccupancyEvent.TOPIC, self._on_occupancy)
        self._bus.subscribe_message(m.NfcScanEvent.TOPIC, self._on_nfc)
        self._bus.subscribe_message(m.DurationDialEvent.TOPIC, self._on_duration)
        self._bus.subscribe_message(m.GateMotionEvent.TOPIC, self._on_gate_motion)
        self._bus.subscribe_message(m.VehicleMoveCommand.TOPIC, self._on_vehicle_move)
        self._bus.subscribe_message(m.ParkingAssignmentCommand.TOPIC, self._on_assignment)
        self._bus.subscribe_message(m.ExitAuthorizationCommand.TOPIC, self._on_exit_authorization)
        self._bus.subscribe_message(m.AdmissionResult.TOPIC, self._on_admission_result)

    def stop(self) -> None:
        ...

    def _on_duration(self, msg: m.DurationDialEvent) -> None:
        self._latest_duration = msg.minutes

    def _on_gate_motion(self, msg: m.GateMotionEvent) -> None:
        self._gate_present = msg.present
        if not msg.present:
            self._complete_departures()

    def _on_nfc(self, msg: m.NfcScanEvent) -> None:
        customer = self._store.customer_for(msg.uid)
        if customer is None:
            customer = Customer(uid=msg.uid, vehicle_uid=_vehicle_uid_for(msg.uid))

        if msg.reader == m.READER_GATE:
            customer.vehicle_uid = customer.vehicle_uid or _vehicle_uid_for(msg.uid)
            customer.expected_minutes = self._latest_duration
            customer.ready_for_pickup = False
            customer.checkout_requested = False
            customer.assigned_spot = ""
            customer.assigned_buffer = ""
            customer.status = ARRIVAL_REQUESTED
            customer.requested_at = msg.ts
            self._store.set_vehicle_spot(customer.vehicle_uid, OUTSIDE)
            self._latest_duration = None
        elif msg.reader == m.READER_CHECKOUT:
            customer.checkout_requested = True
            customer.requested_at = msg.ts
            location = self._store.spot_of_vehicle(customer.vehicle_uid)
            if customer.status in (IN_BUFFER, ENTRY_AUTHORIZED) and location != OUTSIDE:
                customer.status = READY_FOR_PICKUP
                customer.ready_for_pickup = True
            elif customer.status == PARKED:
                customer.status = PICKUP_REQUESTED
            elif customer.status == PARKING:
                # Finish the in-progress move to a known location, then retrieve.
                pass
        self._store.upsert_customer(customer)

    def _on_assignment(self, msg: m.ParkingAssignmentCommand) -> None:
        customer = self._customer_by_vehicle(msg.vehicle_uid)
        if customer is None:
            return
        customer.assigned_spot = msg.spot_id
        customer.assigned_buffer = msg.buffer_id
        customer.status = ENTRY_AUTHORIZED
        self._store.upsert_customer(customer)

    def _on_exit_authorization(self, msg: m.ExitAuthorizationCommand) -> None:
        customer = self._customer_by_vehicle(msg.vehicle_uid)
        if customer is not None:
            customer.status = EXIT_AUTHORIZED
            self._store.upsert_customer(customer)

    def _on_admission_result(self, msg: m.AdmissionResult) -> None:
        if msg.accepted:
            return
        customer = self._customer_by_vehicle(msg.vehicle_uid)
        if customer is not None and customer.status == ARRIVAL_REQUESTED:
            customer.status = REJECTED
            self._store.remove_vehicle(customer.vehicle_uid)
            self._store.upsert_customer(customer)

    def _on_vehicle_move(self, msg: m.VehicleMoveCommand) -> None:
        customer = self._customer_by_vehicle(msg.vehicle_uid)
        if customer is None:
            return
        self._pending_moves[msg.vehicle_uid] = msg
        if customer.assigned_spot and msg.from_spot == customer.assigned_spot:
            # Retrieval chooses a buffer at the time checkout is planned. A
            # parked/shopping customer must not keep a long-lived buffer
            # reservation, so the selected buffer is captured from the move.
            customer.assigned_buffer = msg.to_spot
            customer.status = RETRIEVING
        else:
            customer.status = PARKING
        self._store.upsert_customer(customer)

    def _on_occupancy(self, msg: m.OccupancyEvent) -> None:
        self._store.set_occupancy(msg.spot_id, msg.occupied)

        if msg.occupied:
            entrant = self._oldest_customer(ENTRY_AUTHORIZED, assigned_buffer=msg.spot_id)
            if entrant is not None:
                entrant.status = READY_FOR_PICKUP if entrant.checkout_requested else IN_BUFFER
                entrant.ready_for_pickup = entrant.checkout_requested
                self._store.set_vehicle_spot(entrant.vehicle_uid, msg.spot_id)
                self._store.upsert_customer(entrant)

        # A physical move is confirmed only when both sensor observations are
        # true: the source is free and the commanded destination is occupied.
        # Events may arrive in either order, so re-check every pending move
        # after every occupancy change.
        self._complete_pending_moves()

        if not msg.occupied:
            self._complete_departures()

    def _complete_pending_moves(self) -> None:
        for vehicle_uid, move in list(self._pending_moves.items()):
            if self._store.is_occupied(move.from_spot) or not self._store.is_occupied(move.to_spot):
                continue
            customer = self._customer_by_vehicle(vehicle_uid)
            if customer is None:
                self._pending_moves.pop(vehicle_uid, None)
                continue
            self._store.set_vehicle_spot(vehicle_uid, move.to_spot)
            if move.to_spot == customer.assigned_buffer:
                customer.status = READY_FOR_PICKUP
                customer.ready_for_pickup = True
                # The parking space is no longer reserved once retrieval has
                # been physically confirmed at the buffer.
                customer.assigned_spot = ""
            else:
                customer.status = PICKUP_REQUESTED if customer.checkout_requested else PARKED
                # The entry buffer reservation ends once the car is physically
                # parked. From this point B1 is available for another arrival
                # or retrieval until this customer actually checks out.
                customer.assigned_buffer = ""
            self._store.upsert_customer(customer)
            self._pending_moves.pop(vehicle_uid, None)

    def _complete_departures(self) -> None:
        if self._gate_present:
            return
        for customer in self._store.customers():
            buffer_id = customer.assigned_buffer
            if not buffer_id or self._store.is_occupied(buffer_id):
                continue
            if customer.status == EXIT_AUTHORIZED and self._store.spot_of_vehicle(customer.vehicle_uid) == buffer_id:
                customer.status = DEPARTED
                customer.ready_for_pickup = False
                customer.checkout_requested = False
                customer.assigned_spot = ""
                customer.assigned_buffer = ""
                self._store.remove_vehicle(customer.vehicle_uid)
                self._store.upsert_customer(customer)

    def _customer_by_vehicle(self, vehicle_uid: str) -> Customer | None:
        return next((c for c in self._store.customers() if c.vehicle_uid == vehicle_uid), None)

    def _oldest_customer(self, status: str, assigned_buffer: str = "") -> Customer | None:
        matches = [
            c for c in self._store.customers()
            if c.status == status and (not assigned_buffer or c.assigned_buffer == assigned_buffer)
        ]
        return min(matches, key=lambda c: c.requested_at) if matches else None
