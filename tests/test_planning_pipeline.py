"""Problem generation, STRIPS search, and the event-driven planner pipeline."""
from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.dispatching import PlanDispatcher
from parking.planning import ForwardSearchPlanner, PlannerService, PlanningError
from parking.problem_generation import PddlProblemGenerator, ProblemGenerationService
from parking.simulation import RecordingActuators
from parking.storage import Customer, InMemoryStore, StorageService


def test_generator_and_forward_search_plan_a_parking_move():
    store = InMemoryStore()
    store.upsert_customer(Customer(uid="C1", vehicle_uid="V1", expected_minutes=20))
    store.set_vehicle_spot("V1", "B1")
    store.set_occupancy("B1", True)

    problem = PddlProblemGenerator().generate(store)
    plan = ForwardSearchPlanner().solve(problem)

    assert "(:domain parking)" in problem.pddl
    assert "(at V1 P1)" in problem.pddl
    assert plan.actions == [{"name": "park", "args": ["V1", "B1", "P1"]}]


def test_shorter_stays_receive_nearer_free_spots():
    store = InMemoryStore()
    store.upsert_customer(Customer(uid="C1", vehicle_uid="V1", expected_minutes=90))
    store.upsert_customer(Customer(uid="C2", vehicle_uid="V2", expected_minutes=15))
    store.set_vehicle_spot("V1", "B1")
    store.set_vehicle_spot("V2", "B2")
    store.set_occupancy("B1", True)
    store.set_occupancy("B2", True)

    problem = PddlProblemGenerator(buffers=("B1", "B2")).generate(store)

    assert "(at V2 P1)" in problem.pddl
    assert "(at V1 P2)" in problem.pddl


def test_forward_search_sequences_park_before_retrieve_when_buffer_is_busy():
    store = InMemoryStore()
    store.upsert_customer(Customer(uid="A", vehicle_uid="ARRIVING", expected_minutes=30))
    store.upsert_customer(Customer(uid="L", vehicle_uid="LEAVING", ready_for_pickup=True))
    store.set_vehicle_spot("ARRIVING", "B1")
    store.set_vehicle_spot("LEAVING", "P1")
    store.set_occupancy("B1", True)
    store.set_occupancy("P1", True)

    plan = ForwardSearchPlanner().solve(PddlProblemGenerator().generate(store))

    assert plan.actions == [
        {"name": "park", "args": ["ARRIVING", "B1", "P2"]},
        {"name": "retrieve", "args": ["LEAVING", "P1", "B1"]},
    ]


def test_full_event_pipeline_parks_and_retrieves_a_vehicle():
    bus = MemoryBus()
    store = InMemoryStore()
    components = [
        StorageService(bus, store),
        PlannerService(bus, ForwardSearchPlanner()),
        ProblemGenerationService(bus, store, PddlProblemGenerator()),
        PlanDispatcher(bus),
    ]
    actuators = RecordingActuators(bus)
    for component in components:
        component.start()

    bus.publish_message(m.DurationDialEvent(minutes=25))
    bus.publish_message(m.NfcScanEvent(uid="CAR1", reader=m.READER_GATE))
    assert [(x.vehicle_uid, x.from_spot, x.to_spot) for x in actuators.vehicle_moves] == [
        ("CAR1", "B1", "P1")
    ]
    assert store.spot_of_vehicle("CAR1") == "P1"

    bus.publish_message(m.NfcScanEvent(uid="CAR1", reader=m.READER_CHECKOUT))
    assert [(x.vehicle_uid, x.from_spot, x.to_spot) for x in actuators.vehicle_moves] == [
        ("CAR1", "B1", "P1"),
        ("CAR1", "P1", "B1"),
    ]
    assert store.spot_of_vehicle("CAR1") == "B1"


def test_planner_reports_an_unsolvable_problem():
    problem = m.ProblemMessage(
        problem_id="blocked",
        pddl="""
        (define (problem blocked)
          (:domain parking)
          (:objects V1 - car P1 - spot B1 - buffer)
          (:init (in-buffer V1 B1))
          (:goal (and (at V1 P1))))
        """,
    )

    try:
        ForwardSearchPlanner().solve(problem)
    except PlanningError as exc:
        assert "no solution" in str(exc)
    else:
        raise AssertionError("expected an unsolvable problem to fail")
