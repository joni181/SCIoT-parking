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
            customer = Customer(uid=msg.uid, vehicle_uid=msg.uid)

        if msg.reader == m.READER_GATE:
            customer.vehicle_uid = customer.vehicle_uid or msg.uid
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
        customer.status = RETRIEVING if msg.to_spot == customer.assigned_buffer else PARKING
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

            for vehicle_uid, move in list(self._pending_moves.items()):
                if move.to_spot != msg.spot_id:
                    continue
                customer = self._customer_by_vehicle(vehicle_uid)
                if customer is None:
                    continue
                self._store.set_vehicle_spot(vehicle_uid, msg.spot_id)
                if msg.spot_id == customer.assigned_buffer:
                    customer.status = READY_FOR_PICKUP
                    customer.ready_for_pickup = True
                else:
                    customer.status = PICKUP_REQUESTED if customer.checkout_requested else PARKED
                self._store.upsert_customer(customer)
                self._pending_moves.pop(vehicle_uid, None)

        if not msg.occupied:
            self._complete_departures()

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
