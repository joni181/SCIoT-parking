"""Dashboard projection and HTTP rendering tests."""
from __future__ import annotations

import pytest

from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.storage import Customer, InMemoryStore, PARKING, StorageService
from parking.visualization import DashboardModel, create_dashboard_app


def _dashboard(max_activity=100):
    bus = MemoryBus()
    store = InMemoryStore()
    storage = StorageService(bus, store)
    storage.start()
    model = DashboardModel(bus, store, ("P1", "P2", "P3"), ("B1",), max_activity=max_activity)
    model.start()
    return bus, store, model


def test_snapshot_combines_store_assignments_and_bus_health():
    bus, store, model = _dashboard()
    customer = Customer(
        uid="CARD-A", vehicle_uid="CAR-A", expected_minutes=25,
        assigned_buffer="B1", assigned_spot="P1", status="parked",
    )
    store.upsert_customer(customer)
    store.set_vehicle_spot("CAR-A", "P1")
    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))
    bus.publish_message(m.GateCommand(action=m.GATE_OPEN))
    bus.publish_message(m.GateMotionEvent(present=True))

    snapshot = model.snapshot()

    assert snapshot.connected is True
    assert snapshot.gate_state == "open"
    assert snapshot.gate_present is True
    assert snapshot.free_count == 2
    assert snapshot.occupied_count == 1
    assert snapshot.active_requests == 1
    assert snapshot.parking_spots[0].state == "occupied"
    assert snapshot.parking_spots[0].vehicle_uid == "CAR-A"
    assert snapshot.buffer_spots[0].state == "free"
    assert snapshot.buffer_spots[0].assigned_vehicle == ""
    assert snapshot.assignments[0].assigned_buffer == ""
    assert snapshot.assignments[0].status_label == "Parked"
    assert snapshot.operator_instruction.mode == "idle"
    assert snapshot.operator_instruction.title == "No action required"
    assert "shopping" in snapshot.operator_instruction.detail


def test_plan_admission_movement_and_activity_are_projected():
    bus, store, model = _dashboard(max_activity=4)
    store.upsert_customer(Customer(
        uid="CARD-A", vehicle_uid="CAR-A", assigned_buffer="B1",
        assigned_spot="P2", status=PARKING,
    ))
    store.set_vehicle_spot("CAR-A", "B1")
    store.set_occupancy("B1", True)
    bus.publish_message(m.ProblemMessage(
        problem_id="prob-7", request_uid="CAR-A", purpose="park", pddl="x"
    ))
    bus.publish_message(m.PlanMessage(
        problem_id="prob-7", actions=[{"name": "park", "args": ["CAR-A", "B1", "P2"]}]
    ))
    bus.publish_message(m.AdmissionResult(
        vehicle_uid="CAR-A", accepted=True, assigned_spot="P2"
    ))
    bus.publish_message(m.VehicleMoveCommand(
        vehicle_uid="CAR-A", from_spot="B1", to_spot="P2"
    ))
    bus.publish_message(m.DurationDialEvent(minutes=25))

    snapshot = model.snapshot()

    assert snapshot.latest_plan.problem_id == "prob-7"
    assert snapshot.latest_plan.purpose == "park"
    assert snapshot.latest_plan.actions[0].args == ("CAR-A", "B1", "P2")
    assert snapshot.latest_admission.accepted is True
    assert snapshot.parking_spots[1].state == "moving"
    assert snapshot.buffer_spots[0].state == "occupied"
    assert snapshot.operator_instruction.mode == "action"
    assert snapshot.operator_instruction.from_spot == "B1"
    assert snapshot.operator_instruction.to_spot == "P2"
    assert [item.confirmed for item in snapshot.operator_instruction.confirmations] == [False, False]
    assert len(snapshot.activity) == 4
    assert snapshot.activity[0].message_type == "duration_dial"


def test_rejection_and_unknown_occupant_remain_visible():
    bus, _store, model = _dashboard()
    bus.publish_message(m.OccupancyEvent(spot_id="P3", occupied=True))
    bus.publish_message(m.AdmissionResult(
        vehicle_uid="CAR-X", accepted=False, reason="problem has no solution"
    ))

    snapshot = model.snapshot()
    assert snapshot.parking_spots[2].state == "occupied"
    assert snapshot.parking_spots[2].vehicle_uid == ""
    assert snapshot.latest_admission.reason == "problem has no solution"


def test_dash_app_serves_root_without_opening_browser():
    pytest.importorskip("dash")
    _bus, _store, model = _dashboard()
    app = create_dashboard_app(model)

    response = app.server.test_client().get("/")
    layout = app.server.test_client().get("/_dash-layout")
    stylesheet = app.server.test_client().get("/assets/dashboard.css")

    assert response.status_code == 200
    assert layout.status_code == 200
    assert stylesheet.status_code == 200
    assert b"Parking control center" in layout.data
