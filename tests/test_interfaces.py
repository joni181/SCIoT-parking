"""The module interfaces are real: every stub (and the simulation stand-ins)
actually satisfies the port it claims.

Because the ports are `@runtime_checkable` Protocols, an `isinstance` check
verifies the object exposes the interface's methods. These tests are the guard
that keeps the scaffolded drivers and the contracts in `*/base.py` from drifting
apart as the real implementations land.
"""
from parking.common import Component
from parking.common import models as m
from parking.common.messaging import MemoryBus

from parking.actuators import Actuator, BufferLed, GateMotor, VehicleMover
from parking.dispatching import Dispatcher, PlanDispatcher
from parking.planning import ForwardSearchPlanner, Planner
from parking.problem_generation import PddlProblemGenerator, ProblemGenerator
from parking.sensors import DurationDial, NfcReader, OccupancySensor, Sensor
from parking.storage import Customer, InMemoryStore, OccupancyStore, StateStore, StorageService
from parking.simulation import OccupancyTracker, ReactiveGateController, RecordingActuators
from parking.visualization import ConsoleLotView, DashboardModel, DashboardView, View


def test_sensor_drivers_implement_sensor():
    bus = MemoryBus()
    assert isinstance(OccupancySensor(bus, "P1"), Sensor)
    assert isinstance(NfcReader(bus), Sensor)
    assert isinstance(DurationDial(bus), Sensor)


def test_actuator_drivers_implement_actuator():
    bus = MemoryBus()
    assert isinstance(GateMotor(bus), Actuator)
    assert isinstance(BufferLed(bus), Actuator)
    assert isinstance(VehicleMover(bus), Actuator)


def test_dispatcher_implements_interface():
    assert isinstance(PlanDispatcher(MemoryBus()), Dispatcher)


def test_store_implements_interface():
    assert isinstance(InMemoryStore(), StateStore)


def test_problem_generator_and_planner_implement_interfaces():
    assert isinstance(PddlProblemGenerator(), ProblemGenerator)
    assert isinstance(ForwardSearchPlanner(), Planner)


def test_view_implements_interface():
    bus = MemoryBus()
    assert isinstance(ConsoleLotView(bus), View)
    model = DashboardModel(bus, InMemoryStore(), ("P1",), ("B1",))
    assert isinstance(DashboardView(model, open_browser=False), View)


def test_simulation_standins_implement_their_ports():
    bus = MemoryBus()
    assert isinstance(RecordingActuators(bus), Actuator)
    assert isinstance(OccupancyTracker(bus), OccupancyStore)
    assert isinstance(ReactiveGateController(bus), Component)


def test_pddl_domain_declares_valid_core_requirements():
    with open("parking/planning/domain/domain.pddl", encoding="utf-8") as domain:
        requirements = domain.read()
    assert ":strips" in requirements
    assert ":strict" not in requirements


def test_in_memory_store_roundtrips():
    store = InMemoryStore()
    store.set_occupancy("P1", True)
    assert store.is_occupied("P1") is True
    assert store.free_spots(["P1", "P2", "P3"]) == ["P2", "P3"]

    store.upsert_customer(Customer(uid="AB12CD34", vehicle_uid="V1", expected_minutes=45))
    store.set_vehicle_spot("V1", "P2")
    assert store.customer_for("AB12CD34").expected_minutes == 45
    assert store.spot_of_vehicle("V1") == "P2"
    assert store.customer_for("nope") is None


def test_stub_pipeline_problem_to_plan_runs():
    """The seams connect end-to-end even while the bodies are TODO stubs."""
    store = InMemoryStore()
    problem = PddlProblemGenerator().generate(store)
    plan = ForwardSearchPlanner().solve(problem)
    assert plan.problem_id == problem.problem_id
    # An empty plan is a valid no-op for the dispatcher.
    PlanDispatcher(MemoryBus()).execute(plan)


def test_storage_service_updates_store_from_bus():
    """The laptop's StorageService keeps a real StateStore current from events."""
    bus = MemoryBus()
    store = InMemoryStore()
    service = StorageService(bus, store)
    assert isinstance(service, Component)
    service.start()

    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))
    assert store.occupied_spots() == ["P1"]

    bus.publish_message(m.NfcScanEvent(uid="AB12CD34", reader=m.READER_GATE))
    assert store.customer_for("AB12CD34") is not None
