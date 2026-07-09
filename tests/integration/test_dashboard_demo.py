"""Real-broker smoke test for the guided dashboard runtime."""
from __future__ import annotations

import socket
import time
import urllib.request

import pytest

pytest.importorskip("amqtt")
pytest.importorskip("paho.mqtt.client")
pytest.importorskip("dash")

from parking.simulation import GuidedScenarioController, MqttDemoSystem
from parking.visualization import DashboardView

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.mark.parametrize(
    ("scenario_id", "expected_statuses"),
    [
        ("lifecycle", {"CAR-A": "departed"}),
        ("contention", {"CAR-A": "departed", "CAR-B": "departed"}),
        ("full_lot", {"CAR-C": "rejected"}),
    ],
)
def test_guided_scenarios_over_real_mqtt_serve_dashboard(
    mqtt_broker, scenario_id, expected_statuses
):
    controller = GuidedScenarioController(
        lambda: MqttDemoSystem("127.0.0.1", mqtt_broker),
    )
    view = DashboardView(
        controller.source,
        host="127.0.0.1",
        port=_free_port(),
        open_browser=False,
        demo_controller=controller,
    )
    try:
        view.start()
        with urllib.request.urlopen(view.url, timeout=3) as response:
            assert response.status == 200
        controller.start_scenario(scenario_id)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and controller.status().state not in ("completed", "failed"):
            if controller.status().state == "waiting_for_advance":
                controller.advance()
            time.sleep(0.05)
        assert controller.status().state == "completed", controller.status()
        assignments = controller.source.snapshot().assignments
        actual = {item.vehicle_uid: item.status for item in assignments}
        assert actual | expected_statuses == actual
    finally:
        view.stop()
        controller.close()


def test_guided_controller_waits_for_advance_and_reset(mqtt_broker):
    controller = GuidedScenarioController(
        lambda: MqttDemoSystem("127.0.0.1", mqtt_broker),
    )
    try:
        controller.start_scenario("lifecycle")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and controller.status().state != "waiting_for_advance":
            time.sleep(0.02)

        waiting_step = controller.status().step
        assert waiting_step == 1
        time.sleep(0.2)
        assert controller.status().step == waiting_step

        controller.advance()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and controller.status().step < 2:
            time.sleep(0.02)
        assert controller.status().state == "waiting_for_advance"
        instruction = controller.source.snapshot().operator_instruction
        assert instruction.mode == "action"
        assert instruction.title == "Bring arriving vehicle into the buffer"

        controller.advance()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and controller.status().step < 3:
            time.sleep(0.02)
        instruction = controller.source.snapshot().operator_instruction
        assert instruction.mode == "action"
        assert instruction.from_spot == "B1"
        assert instruction.to_spot == "P1"

        controller.reset()
        assert controller.status().state == "idle"
        assert controller.source.snapshot().assignments == ()
    finally:
        controller.close()


def test_contention_releases_buffer_while_first_customer_shops(mqtt_broker):
    controller = GuidedScenarioController(
        lambda: MqttDemoSystem("127.0.0.1", mqtt_broker),
    )
    try:
        controller.start_scenario("contention")

        _advance_to_waiting_step(controller, 4)
        snapshot = controller.source.snapshot()
        assignments = {item.vehicle_uid: item for item in snapshot.assignments}
        assert assignments["CAR-A"].assigned_buffer == ""
        assert assignments["CAR-A"].assigned_spot == "P1"
        assert snapshot.buffer_spots[0].state == "free"
        assert snapshot.buffer_spots[0].assigned_vehicle == ""

        controller.advance()
        _wait_for_waiting_step(controller, 5)
        snapshot = controller.source.snapshot()
        assert snapshot.buffer_spots[0].state == "assigned"
        assert snapshot.buffer_spots[0].assigned_vehicle == "CAR-B"
    finally:
        controller.close()


def test_contention_reset_restarts_from_empty_runtime(mqtt_broker):
    controller = GuidedScenarioController(
        lambda: MqttDemoSystem("127.0.0.1", mqtt_broker),
    )
    try:
        controller.start_scenario("contention")
        _advance_to_waiting_step(controller, 4)
        controller.reset()
        snapshot = controller.source.snapshot()
        assert controller.status().state == "idle"
        assert snapshot.assignments == ()
        assert all(spot.state == "free" for spot in (*snapshot.buffer_spots, *snapshot.parking_spots))

        controller.start_scenario("contention")
        _complete_with_auto_advance(controller)
        assert controller.status().state == "completed"
    finally:
        controller.close()


def _advance_to_waiting_step(controller: GuidedScenarioController, step: int) -> None:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        status = controller.status()
        if status.state == "failed":
            raise AssertionError(status)
        if status.state == "waiting_for_advance" and status.step == step:
            return
        if status.state == "waiting_for_advance":
            controller.advance()
        time.sleep(0.03)
    raise AssertionError(controller.status())


def _wait_for_waiting_step(controller: GuidedScenarioController, step: int) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        status = controller.status()
        if status.state == "failed":
            raise AssertionError(status)
        if status.state == "waiting_for_advance" and status.step == step:
            return
        time.sleep(0.03)
    raise AssertionError(controller.status())


def _complete_with_auto_advance(controller: GuidedScenarioController) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and controller.status().state not in ("completed", "failed"):
        if controller.status().state == "waiting_for_advance":
            controller.advance()
        time.sleep(0.03)
    if controller.status().state != "completed":
        raise AssertionError(controller.status())
