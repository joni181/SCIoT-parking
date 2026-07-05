"""Planner workflow scenarios, including physical sensor confirmations."""
from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.dispatching import GateSafetyController, PlanDispatcher
from parking.planning import ForwardSearchPlanner, PlannerService
from parking.problem_generation import PddlProblemGenerator, ProblemGenerationService
from parking.simulation import RecordingActuators
from parking.storage import (
    ARRIVAL_REQUESTED,
    DEPARTED,
    ENTRY_AUTHORIZED,
    EXIT_AUTHORIZED,
    IN_BUFFER,
    OUTSIDE,
    PARKED,
    PICKUP_REQUESTED,
    READY_FOR_PICKUP,
    REJECTED,
    RETRIEVING,
    Customer,
    InMemoryStore,
    StorageService,
)


def _system(spots=("P1", "P2", "P3")):
    bus = MemoryBus()
    store = InMemoryStore()
    components = [
        StorageService(bus, store),
        PlannerService(bus, ForwardSearchPlanner()),
        ProblemGenerationService(bus, store, PddlProblemGenerator(spots=spots)),
        PlanDispatcher(bus),
        GateSafetyController(bus),
    ]
    actuators = RecordingActuators(bus)
    for component in components:
        component.start()
    return bus, store, actuators


def _customer(store, uid):
    customer = store.customer_for(uid)
    assert customer is not None
    return customer


def _admit(bus, uid="CAR1", minutes=25):
    bus.publish_message(m.DurationDialEvent(minutes=minutes))
    bus.publish_message(m.GateMotionEvent(present=True))
    bus.publish_message(m.NfcScanEvent(uid=uid, reader=m.READER_GATE))


def _confirm_parked(bus, spot="P1"):
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=True))
    bus.publish_message(m.GateMotionEvent(present=False))
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=False))
    bus.publish_message(m.OccupancyEvent(spot_id=spot, occupied=True))


def test_arrival_plan_assigns_opens_gate_and_shows_spot():
    store = InMemoryStore()
    store.upsert_customer(Customer(uid="C1", vehicle_uid="V1", status=ARRIVAL_REQUESTED))
    store.set_vehicle_spot("V1", OUTSIDE)

    problem = PddlProblemGenerator().generate(store)
    plan = ForwardSearchPlanner().solve(problem)

    assert problem.purpose == "arrival"
    assert plan.actions == [
        {"name": "assign", "args": ["V1", "P1"]},
        {"name": "open-entry", "args": ["V1", "B1", "P1"]},
        {"name": "show-assignment", "args": ["V1", "P1", "B1"]},
    ]


def test_expected_duration_influences_spot_distance():
    store = InMemoryStore()
    store.upsert_customer(Customer(
        uid="C1", vehicle_uid="V1", expected_minutes=90, status=ARRIVAL_REQUESTED
    ))
    store.set_vehicle_spot("V1", OUTSIDE)

    plan = ForwardSearchPlanner().solve(PddlProblemGenerator().generate(store))

    assert plan.actions[0] == {"name": "assign", "args": ["V1", "P2"]}


def test_full_arrival_and_checkout_cycle_waits_for_sensor_confirmation():
    bus, store, actuators = _system()
    _admit(bus)

    assert _customer(store, "CAR1").status == ENTRY_AUTHORIZED
    assert actuators.gate_state == m.GATE_OPEN
    assert actuators.spot_displays[-1].spot_id == "P1"
    assert actuators.admission_results[-1].accepted is True
    assert actuators.vehicle_moves == []

    # Entering the buffer is the physical confirmation that unlocks parking.
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=True))
    assert _customer(store, "CAR1").status != PARKED
    assert [(x.from_spot, x.to_spot) for x in actuators.vehicle_moves] == [("B1", "P1")]

    bus.publish_message(m.GateMotionEvent(present=False))
    assert actuators.gate_state == m.GATE_CLOSE
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=False))
    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))
    assert _customer(store, "CAR1").status == PARKED

    bus.publish_message(m.NfcScanEvent(uid="CAR1", reader=m.READER_CHECKOUT))
    assert _customer(store, "CAR1").status != READY_FOR_PICKUP
    assert actuators.vehicle_moves[-1].from_spot == "P1"
    assert actuators.vehicle_moves[-1].to_spot == "B1"

    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=False))
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=True))
    assert _customer(store, "CAR1").status == EXIT_AUTHORIZED
    assert actuators.gate_state == m.GATE_OPEN

    bus.publish_message(m.GateMotionEvent(present=True))
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=False))
    bus.publish_message(m.GateMotionEvent(present=False))
    assert _customer(store, "CAR1").status == DEPARTED
    assert actuators.gate_state == m.GATE_CLOSE


def test_checkout_during_parking_is_retained_then_retrieved():
    bus, store, actuators = _system()
    _admit(bus)
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=True))

    # The move command is already active. Checkout is retained instead of lost;
    # the safe policy completes that move before issuing retrieval.
    bus.publish_message(m.NfcScanEvent(uid="CAR1", reader=m.READER_CHECKOUT))
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=False))
    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))

    assert _customer(store, "CAR1").status == RETRIEVING
    assert [(x.from_spot, x.to_spot) for x in actuators.vehicle_moves] == [
        ("B1", "P1"),
        ("P1", "B1"),
    ]


def test_checkout_before_parking_starts_skips_unnecessary_parking():
    bus, store, actuators = _system()
    _admit(bus)

    # Checkout arrives after admission but before the car reaches the buffer.
    bus.publish_message(m.NfcScanEvent(uid="CAR1", reader=m.READER_CHECKOUT))
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=True))

    assert _customer(store, "CAR1").status == EXIT_AUTHORIZED
    assert actuators.vehicle_moves == []
    assert actuators.gate_state == m.GATE_OPEN


def test_second_checkout_waits_until_first_vehicle_leaves_buffer():
    bus, store, actuators = _system()
    # A is ready in the only buffer; B is parked and checks out.
    a = Customer(uid="A", vehicle_uid="A", status=EXIT_AUTHORIZED, assigned_buffer="B1")
    b = Customer(uid="B", vehicle_uid="B", status=PARKED, assigned_buffer="B1", assigned_spot="P2")
    store.upsert_customer(a)
    store.upsert_customer(b)
    store.set_vehicle_spot("A", "B1")
    store.set_vehicle_spot("B", "P2")
    store.set_occupancy("B1", True)
    store.set_occupancy("P2", True)

    bus.publish_message(m.NfcScanEvent(uid="B", reader=m.READER_CHECKOUT))
    assert _customer(store, "B").status == PICKUP_REQUESTED
    assert actuators.vehicle_moves == []

    # A leaves; the occupancy change replans and starts B's retrieval.
    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=False))
    assert _customer(store, "A").status == DEPARTED
    assert [(x.vehicle_uid, x.from_spot, x.to_spot) for x in actuators.vehicle_moves] == [
        ("B", "P2", "B1")
    ]


def test_arrival_is_rejected_when_no_spot_is_available():
    bus, store, actuators = _system(spots=("P1",))
    store.set_occupancy("P1", True)

    _admit(bus)

    assert _customer(store, "CAR1").status == REJECTED
    assert actuators.admission_results[-1].accepted is False
    assert actuators.gate_state is None
