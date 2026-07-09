"""Thread-safe read model for the laptop operator dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Iterable

from ..common import models as m, topics
from ..common.messaging import MessageBus
from ..storage import (
    ARRIVAL_REQUESTED,
    DEPARTED,
    ENTRY_AUTHORIZED,
    EXIT_AUTHORIZED,
    IN_BUFFER,
    PARKED,
    PARKING,
    PICKUP_REQUESTED,
    READY_FOR_PICKUP,
    REJECTED,
    RETRIEVING,
    Customer,
    StateStore,
)


STATUS_LABELS = {
    "arrival_requested": "Arrival requested",
    "entry_authorized": "Entry authorized",
    "in_buffer": "In entrance buffer",
    "parking": "Moving to parking spot",
    "parked": "Parked",
    "pickup_requested": "Pickup requested",
    "retrieving": "Retrieving vehicle",
    "ready_for_pickup": "Ready for pickup",
    "exit_authorized": "Exit authorized",
    "departed": "Departed",
    "rejected": "Rejected",
}


@dataclass(frozen=True)
class SpotSnapshot:
    spot_id: str
    kind: str
    state: str
    occupied: bool
    vehicle_uid: str = ""
    assigned_vehicle: str = ""


@dataclass(frozen=True)
class AssignmentSnapshot:
    uid: str
    vehicle_uid: str
    expected_minutes: int | None
    assigned_buffer: str
    assigned_spot: str
    current_location: str
    status: str
    status_label: str
    requested_at: float


@dataclass(frozen=True)
class PlanActionSnapshot:
    index: int
    name: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class PlanSnapshot:
    problem_id: str = ""
    purpose: str = ""
    vehicle_uid: str = ""
    actions: tuple[PlanActionSnapshot, ...] = ()


@dataclass(frozen=True)
class AdmissionSnapshot:
    vehicle_uid: str = ""
    accepted: bool | None = None
    reason: str = ""
    assigned_spot: str = ""


@dataclass(frozen=True)
class ActivitySnapshot:
    timestamp: float
    kind: str
    message_type: str
    summary: str


@dataclass(frozen=True)
class ConfirmationSnapshot:
    label: str
    confirmed: bool


@dataclass(frozen=True)
class OperatorInstructionSnapshot:
    mode: str
    title: str
    detail: str
    vehicle_uid: str = ""
    from_spot: str = ""
    to_spot: str = ""
    confirmations: tuple[ConfirmationSnapshot, ...] = ()


@dataclass(frozen=True)
class DashboardSnapshot:
    connected: bool
    gate_state: str
    gate_present: bool
    parking_spots: tuple[SpotSnapshot, ...]
    buffer_spots: tuple[SpotSnapshot, ...]
    assignments: tuple[AssignmentSnapshot, ...]
    occupied_count: int
    free_count: int
    active_requests: int
    operator_instruction: OperatorInstructionSnapshot
    latest_plan: PlanSnapshot
    latest_admission: AdmissionSnapshot
    activity: tuple[ActivitySnapshot, ...]
    version: int


class DashboardModel:
    """Project bus traffic and the shared store into immutable UI snapshots."""

    def __init__(
        self,
        bus: MessageBus,
        store: StateStore,
        parking_spots: Iterable[str],
        buffer_spots: Iterable[str],
        max_activity: int = 100,
    ) -> None:
        self._bus = bus
        self._store = store
        self._parking_spots = tuple(parking_spots)
        self._buffer_spots = tuple(buffer_spots)
        self._max_activity = max_activity
        self._lock = RLock()
        self._started = False
        self._version = 0
        self._gate_state = "closed"
        self._gate_present = False
        self._activity: list[ActivitySnapshot] = []
        self._problem_context: dict[str, tuple[str, str]] = {}
        self._latest_plan = PlanSnapshot()
        self._latest_admission = AdmissionSnapshot()
        self._moves: dict[str, m.VehicleMoveCommand] = {}

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        self._bus.subscribe_message(topics.ALL, self._on_message)

    def stop(self) -> None:
        # MessageBus currently has no unsubscribe operation. The owning runtime
        # stops/discards the bus, so there can be no callbacks after shutdown.
        ...

    def render(self) -> None:
        """Mark the projection dirty for View compatibility."""
        with self._lock:
            self._version += 1

    def snapshot(self) -> DashboardSnapshot:
        with self._lock:
            customers = sorted(self._store.customers(), key=lambda c: (c.requested_at, c.uid))
            locations = self._store.vehicle_locations()
            assignments = tuple(self._assignment(c, locations) for c in customers)
            parking = tuple(self._spot(s, "parking", customers, locations) for s in self._parking_spots)
            buffers = tuple(self._spot(s, "buffer", customers, locations) for s in self._buffer_spots)
            occupied_count = sum(spot.occupied for spot in (*parking, *buffers))
            free_count = len(parking) - sum(spot.occupied for spot in parking)
            active = sum(c.status not in (DEPARTED, REJECTED) for c in customers)
            return DashboardSnapshot(
                connected=self._connected(),
                gate_state=self._gate_state,
                gate_present=self._gate_present,
                parking_spots=parking,
                buffer_spots=buffers,
                assignments=assignments,
                occupied_count=occupied_count,
                free_count=free_count,
                active_requests=active,
                operator_instruction=self._instruction(customers, locations),
                latest_plan=self._latest_plan,
                latest_admission=self._latest_admission,
                activity=tuple(reversed(self._activity)),
                version=self._version,
            )

    def _connected(self) -> bool:
        check = getattr(self._bus, "is_connected", None)
        return bool(check()) if callable(check) else True

    def _assignment(self, customer: Customer, locations: dict[str, str]) -> AssignmentSnapshot:
        return AssignmentSnapshot(
            uid=customer.uid,
            vehicle_uid=customer.vehicle_uid,
            expected_minutes=customer.expected_minutes,
            assigned_buffer=self._visible_buffer_assignment(customer),
            assigned_spot=customer.assigned_spot,
            current_location=locations.get(customer.vehicle_uid, ""),
            status=customer.status,
            status_label=STATUS_LABELS.get(customer.status, customer.status.replace("_", " ").title()),
            requested_at=customer.requested_at,
        )

    def _spot(
        self,
        spot_id: str,
        kind: str,
        customers: list[Customer],
        locations: dict[str, str],
    ) -> SpotSnapshot:
        occupied = self._store.is_occupied(spot_id)
        vehicle_uid = next((uid for uid, location in locations.items() if location == spot_id), "")
        assigned = next(
            (
                c.vehicle_uid
                for c in customers
                if c.status not in (DEPARTED, REJECTED)
                and (
                    (kind == "parking" and c.assigned_spot == spot_id)
                    or (
                        kind == "buffer"
                        and self._visible_buffer_assignment(c) == spot_id
                    )
                )
            ),
            "",
        )
        moving = any(
            command.from_spot == spot_id or command.to_spot == spot_id
            for uid, command in self._moves.items()
            if any(c.vehicle_uid == uid and c.status in ("parking", "retrieving") for c in customers)
        )
        state = "occupied" if occupied else "moving" if moving else "assigned" if assigned else "free"
        return SpotSnapshot(spot_id, kind, state, occupied, vehicle_uid, assigned)

    @staticmethod
    def _visible_buffer_assignment(customer: Customer) -> str:
        if customer.status in (
            ENTRY_AUTHORIZED,
            IN_BUFFER,
            RETRIEVING,
            READY_FOR_PICKUP,
            EXIT_AUTHORIZED,
        ):
            return customer.assigned_buffer
        return ""

    def _instruction(
        self, customers: list[Customer], locations: dict[str, str]
    ) -> OperatorInstructionSnapshot:
        active = [c for c in customers if c.status not in (DEPARTED, REJECTED)]

        for status in (PARKING, RETRIEVING):
            customer = next((c for c in active if c.status == status), None)
            if customer is None:
                continue
            move = self._moves.get(customer.vehicle_uid)
            if move is None:
                return OperatorInstructionSnapshot(
                    mode="waiting",
                    title="Waiting for movement instruction",
                    detail=f"The planner is preparing the next task for {customer.vehicle_uid}.",
                    vehicle_uid=customer.vehicle_uid,
                )
            parking = status == PARKING
            return OperatorInstructionSnapshot(
                mode="action",
                title="Move vehicle to parking spot" if parking else "Retrieve vehicle for pickup",
                detail=f"Move {customer.vehicle_uid} from {move.from_spot} to {move.to_spot}.",
                vehicle_uid=customer.vehicle_uid,
                from_spot=move.from_spot,
                to_spot=move.to_spot,
                confirmations=(
                    ConfirmationSnapshot(
                        f"{move.from_spot} is free", not self._store.is_occupied(move.from_spot)
                    ),
                    ConfirmationSnapshot(
                        f"{move.to_spot} is occupied", self._store.is_occupied(move.to_spot)
                    ),
                ),
            )

        customer = next((c for c in active if c.status == ENTRY_AUTHORIZED), None)
        if customer is not None:
            buffer_id = customer.assigned_buffer
            return OperatorInstructionSnapshot(
                mode="action",
                title="Bring arriving vehicle into the buffer",
                detail=(
                    f"Drive {customer.vehicle_uid} into {buffer_id}, stop there, "
                    "and let the customer exit the vehicle."
                ),
                vehicle_uid=customer.vehicle_uid,
                from_spot="Gate",
                to_spot=buffer_id,
                confirmations=(
                    ConfirmationSnapshot("Gate is open", self._gate_state == m.GATE_OPEN),
                    ConfirmationSnapshot(
                        f"{buffer_id} is occupied", self._store.is_occupied(buffer_id)
                    ),
                ),
            )

        customer = next((c for c in active if c.status in (READY_FOR_PICKUP, EXIT_AUTHORIZED)), None)
        if customer is not None:
            buffer_id = customer.assigned_buffer or locations.get(customer.vehicle_uid, "buffer")
            return OperatorInstructionSnapshot(
                mode="ready",
                title="Vehicle ready for customer collection",
                detail=f"{customer.vehicle_uid} is ready at {buffer_id}. The customer may collect it and drive out.",
                vehicle_uid=customer.vehicle_uid,
                from_spot=buffer_id,
                to_spot="Exit",
                confirmations=(
                    ConfirmationSnapshot(
                        f"{buffer_id} is free", not self._store.is_occupied(buffer_id)
                    ),
                    ConfirmationSnapshot("Gate approach is clear", not self._gate_present),
                ),
            )

        customer = next((c for c in active if c.status == IN_BUFFER), None)
        if customer is not None:
            return OperatorInstructionSnapshot(
                mode="waiting",
                title="Vehicle detected in buffer",
                detail=f"{customer.vehicle_uid} is in {customer.assigned_buffer}. Waiting for the parking instruction.",
                vehicle_uid=customer.vehicle_uid,
            )

        customer = next((c for c in active if c.status == PICKUP_REQUESTED), None)
        if customer is not None:
            return OperatorInstructionSnapshot(
                mode="waiting",
                title="Checkout received",
                detail=f"Preparing the retrieval instruction for {customer.vehicle_uid}.",
                vehicle_uid=customer.vehicle_uid,
            )

        customer = next((c for c in active if c.status == ARRIVAL_REQUESTED), None)
        if customer is not None:
            return OperatorInstructionSnapshot(
                mode="waiting",
                title="Planning parking assignment",
                detail=f"Please wait while a space and buffer are selected for {customer.vehicle_uid}.",
                vehicle_uid=customer.vehicle_uid,
            )

        customer = next((c for c in active if c.status == PARKED), None)
        if customer is not None:
            location = locations.get(customer.vehicle_uid, customer.assigned_spot)
            return OperatorInstructionSnapshot(
                mode="idle",
                title="No action required",
                detail=f"{customer.vehicle_uid} is parked at {location}. The customer is currently shopping.",
                vehicle_uid=customer.vehicle_uid,
                to_spot=location,
            )

        rejected = next((c for c in reversed(customers) if c.status == REJECTED), None)
        if rejected is not None:
            reason = self._latest_admission.reason if self._latest_admission.vehicle_uid == rejected.vehicle_uid else "No parking assignment is available."
            return OperatorInstructionSnapshot(
                mode="error",
                title="Admission rejected",
                detail=f"Do not open the gate for {rejected.vehicle_uid}. {reason}",
                vehicle_uid=rejected.vehicle_uid,
            )

        return OperatorInstructionSnapshot(
            mode="idle",
            title="No action required",
            detail="The system is ready for the next arriving customer.",
        )

    def _on_message(self, message: m.Message) -> None:
        with self._lock:
            self._version += 1
            if isinstance(message, m.GateCommand):
                self._gate_state = message.action
            elif isinstance(message, m.GateMotionEvent):
                self._gate_present = message.present
            elif isinstance(message, m.ProblemMessage):
                self._problem_context[message.problem_id] = (message.purpose, message.request_uid)
                if len(self._problem_context) > 50:
                    self._problem_context.pop(next(iter(self._problem_context)))
            elif isinstance(message, m.PlanMessage):
                purpose, vehicle_uid = self._problem_context.get(message.problem_id, ("", ""))
                self._latest_plan = PlanSnapshot(
                    problem_id=message.problem_id,
                    purpose=purpose,
                    vehicle_uid=vehicle_uid,
                    actions=tuple(
                        PlanActionSnapshot(i + 1, str(action.get("name", "")), tuple(action.get("args", ())))
                        for i, action in enumerate(message.actions)
                    ),
                )
            elif isinstance(message, m.AdmissionResult):
                self._latest_admission = AdmissionSnapshot(
                    message.vehicle_uid, message.accepted, message.reason, message.assigned_spot
                )
            elif isinstance(message, m.VehicleMoveCommand):
                self._moves[message.vehicle_uid] = message

            self._activity.append(ActivitySnapshot(
                timestamp=message.ts,
                kind=_message_kind(message),
                message_type=message.TYPE,
                summary=_message_summary(message),
            ))
            if len(self._activity) > self._max_activity:
                del self._activity[:-self._max_activity]


def _message_kind(message: m.Message) -> str:
    if message.TOPIC.startswith("parking/events/"):
        return "event"
    if message.TOPIC.startswith("parking/commands/"):
        return "command"
    return "planning"


def _message_summary(message: m.Message) -> str:
    if isinstance(message, m.OccupancyEvent):
        return f"{message.spot_id} {'occupied' if message.occupied else 'free'}"
    if isinstance(message, m.GateMotionEvent):
        return f"Gate vehicle {'present' if message.present else 'cleared'}"
    if isinstance(message, m.NfcScanEvent):
        return f"Card {message.uid} scanned at {message.reader}"
    if isinstance(message, m.DurationDialEvent):
        return f"Duration selected: {message.minutes if message.minutes is not None else 'unknown'} min"
    if isinstance(message, m.GateCommand):
        return f"Gate command: {message.action}"
    if isinstance(message, m.VehicleMoveCommand):
        return f"Move {message.vehicle_uid}: {message.from_spot} → {message.to_spot}"
    if isinstance(message, m.ParkingAssignmentCommand):
        return f"Assign {message.vehicle_uid}: {message.buffer_id} → {message.spot_id}"
    if isinstance(message, m.ParkingSpotDisplayCommand):
        return f"Display {message.spot_id} for {message.vehicle_uid}"
    if isinstance(message, m.ExitAuthorizationCommand):
        return f"Exit authorized for {message.vehicle_uid} via {message.buffer_id}"
    if isinstance(message, m.ProblemMessage):
        return f"Planning {message.purpose or 'idle'} for {message.request_uid or 'system'}"
    if isinstance(message, m.PlanMessage):
        return f"Plan {message.problem_id}: {len(message.actions)} action(s)"
    if isinstance(message, m.AdmissionResult):
        outcome = "accepted" if message.accepted else "rejected"
        detail = message.assigned_spot or message.reason
        return f"{message.vehicle_uid} {outcome}{f': {detail}' if detail else ''}"
    return message.TYPE.replace("_", " ").title()
