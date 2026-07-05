"""Message envelope encode/decode round-trips - the wire contract."""
import json

import pytest

from parking.common import models as m


def test_occupancy_round_trip():
    original = m.OccupancyEvent(spot_id="P1", occupied=True, raw_value=820, source="pi/light/P1")
    restored = m.decode(original.encode())
    assert isinstance(restored, m.OccupancyEvent)
    assert restored.spot_id == "P1"
    assert restored.occupied is True
    assert restored.raw_value == 820
    assert restored.source == "pi/light/P1"
    assert restored.ts == original.ts


def test_envelope_shape():
    env = json.loads(m.GateCommand(action=m.GATE_OPEN, source="ctrl").encode())
    assert env["type"] == "gate_cmd"
    assert env["source"] == "ctrl"
    assert "ts" in env
    assert env["data"] == {"action": "open"}


@pytest.mark.parametrize(
    "message",
    [
        m.OccupancyEvent(spot_id="P2", occupied=False),
        m.GateMotionEvent(present=True),
        m.NfcScanEvent(uid="AB12", reader=m.READER_CHECKOUT),
        m.DurationDialEvent(raw_value=512, minutes=30),
        m.GateCommand(action=m.GATE_CLOSE),
        m.BufferLedCommand(slot_id="B1", on=True),
        m.VehicleMoveCommand(vehicle_uid="AB12", from_spot="B1", to_spot="P3"),
        m.ParkingAssignmentCommand(vehicle_uid="AB12", buffer_id="B1", spot_id="P3"),
        m.ParkingSpotDisplayCommand(vehicle_uid="AB12", spot_id="P3", on=True),
        m.ExitAuthorizationCommand(vehicle_uid="AB12", buffer_id="B1"),
        m.ProblemMessage(problem_id="p1", pddl="(define ...)"),
        m.PlanMessage(problem_id="p1", actions=[{"name": "move", "args": ["AB12", "B1", "P3"]}]),
        m.AdmissionResult(vehicle_uid="AB12", accepted=True, assigned_spot="P3"),
    ],
)
def test_every_type_round_trips(message):
    restored = m.decode(message.encode())
    assert type(restored) is type(message)
    assert restored.data() == message.data()


def test_each_message_has_distinct_topic_and_type():
    classes = [
        m.OccupancyEvent, m.GateMotionEvent, m.NfcScanEvent, m.DurationDialEvent,
        m.GateCommand, m.BufferLedCommand, m.VehicleMoveCommand,
        m.ParkingAssignmentCommand, m.ParkingSpotDisplayCommand, m.ExitAuthorizationCommand,
        m.ProblemMessage, m.PlanMessage, m.AdmissionResult,
    ]
    assert len({c.TYPE for c in classes}) == len(classes)
    assert len({c.TOPIC for c in classes}) == len(classes)


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        m.decode(json.dumps({"type": "nope", "data": {}}))
