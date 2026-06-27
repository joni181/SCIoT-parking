"""Both scenarios over a REAL broker with two real MqttBus clients.

This mirrors the live setup: a Pi node and a laptop node, each its own paho
client connected to the broker, talking only through topics. Same broker code
(`amqtt`), same bus code (`MqttBus`), same module logic (`parking.simulation`)
as the deployed system - just on localhost. Compared to the MemoryBus tests it
additionally exercises: JSON-over-the-wire, paho, the network, connection setup,
and MqttBus's subscription de-duplication.
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("amqtt")
pytest.importorskip("paho.mqtt.client")

from parking.common.messaging import MqttBus
from parking.simulation import (
    OccupancyTracker,
    ReactiveGateController,
    RecordingActuators,
    SimulatedSensors,
)

pytestmark = pytest.mark.integration

REGISTERED = "AB12CD34"


def wait_for(predicate, timeout: float = 5.0, interval: float = 0.02) -> bool:
    """Poll ``predicate`` until truthy or ``timeout`` elapses (MQTT is async)."""
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _connected_bus(port: int, client_id: str) -> MqttBus:
    bus = MqttBus(host="127.0.0.1", port=port, client_id=client_id)
    bus.start()
    assert wait_for(bus.is_connected), f"{client_id} never connected"
    return bus


def test_occupancy_pi_to_laptop_over_broker(mqtt_broker):
    """Pi publishes occupancy; the laptop node sees it - across the broker."""
    laptop = _connected_bus(mqtt_broker, "laptop")
    pi = _connected_bus(mqtt_broker, "pi")
    try:
        tracker = OccupancyTracker(laptop)   # laptop side (storage/viz stand-in)
        sensors = SimulatedSensors(pi)       # Pi side
        time.sleep(0.3)                      # let the laptop's subscribe settle

        sensors.car_parks("P1")

        assert wait_for(lambda: tracker.is_occupied("P1"))
        assert tracker.free_spots(["P1", "P2", "P3"]) == ["P2", "P3"]
    finally:
        pi.stop()
        laptop.stop()


def test_gate_opens_for_registered_car_over_broker(mqtt_broker):
    """Sensors -> control -> actuator, all round-tripping through the broker."""
    pi = _connected_bus(mqtt_broker, "pi")
    try:
        # On the Pi: control logic + actuator + sensors, all on the Pi's client.
        ReactiveGateController(pi, known_uids=[REGISTERED])
        actuators = RecordingActuators(pi)
        sensors = SimulatedSensors(pi)
        time.sleep(0.3)

        sensors.car_arrives_at_gate()
        sensors.scan_nfc(REGISTERED)
        assert wait_for(lambda: actuators.gate_state == "open")

        sensors.gate_clear()
        assert wait_for(lambda: actuators.gate_state == "close")
    finally:
        pi.stop()


def test_unknown_card_keeps_gate_shut_over_broker(mqtt_broker):
    pi = _connected_bus(mqtt_broker, "pi")
    try:
        ReactiveGateController(pi, known_uids=[REGISTERED])
        actuators = RecordingActuators(pi)
        sensors = SimulatedSensors(pi)
        time.sleep(0.3)

        sensors.car_arrives_at_gate()
        sensors.scan_nfc("DEADBEEF")
        time.sleep(0.5)  # give any (wrong) command time to arrive

        assert actuators.gate_state is None
    finally:
        pi.stop()
