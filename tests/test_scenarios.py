"""End-to-end message-flow scenarios, run entirely in-process (no hardware).

These are the executable answers to the two driving questions for this branch.
"""
from parking.common.messaging import MemoryBus
from parking.simulation import (
    OccupancyTracker,
    ReactiveGateController,
    RecordingActuators,
    SimulatedSensors,
)

REGISTERED = "AB12CD34"
SPOTS = ["P1", "P2", "P3"]


def test_scenario_car_parks_becomes_visible_to_laptop():
    """A Pi light sensor reports occupancy; the laptop side sees spot P1 taken."""
    bus = MemoryBus()
    tracker = OccupancyTracker(bus)  # stand-in for storage + visualization
    sensors = SimulatedSensors(bus)

    assert tracker.free_spots(SPOTS) == ["P1", "P2", "P3"]

    sensors.car_parks("P1")

    assert tracker.is_occupied("P1") is True
    assert tracker.free_spots(SPOTS) == ["P2", "P3"]

    sensors.car_leaves("P1")
    assert tracker.is_occupied("P1") is False


def test_scenario_registered_car_opens_gate_then_closes():
    """Motion + a registered card at the gate makes the control logic open it."""
    bus = MemoryBus()
    ReactiveGateController(bus, known_uids=[REGISTERED])
    actuators = RecordingActuators(bus)
    sensors = SimulatedSensors(bus)

    sensors.car_arrives_at_gate()
    assert actuators.gate_state is None  # motion alone is not enough

    sensors.scan_nfc(REGISTERED)
    assert actuators.gate_state == "open"  # car present + known card -> open

    sensors.gate_clear()
    assert actuators.gate_state == "close"  # car passed -> close behind it


def test_scenario_unknown_card_keeps_gate_shut():
    bus = MemoryBus()
    ReactiveGateController(bus, known_uids=[REGISTERED])
    actuators = RecordingActuators(bus)
    sensors = SimulatedSensors(bus)

    sensors.car_arrives_at_gate()
    sensors.scan_nfc("DEADBEEF")

    assert actuators.gate_state is None
    assert actuators.gate_commands == []
