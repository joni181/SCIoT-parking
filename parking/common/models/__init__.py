"""Shared message schemas exchanged over the bus.

Import message types and the codec from here:

    from parking.common import models as m
    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))
"""
from .messages import (
    GATE_CLOSE,
    GATE_OPEN,
    READER_CHECKOUT,
    READER_GATE,
    BufferLedCommand,
    AdmissionResult,
    DistanceEvent,
    DurationDialEvent,
    GateCommand,
    GateMotionEvent,
    LotFullCommand,
    Message,
    NfcScanEvent,
    OccupancyEvent,
    PlanMessage,
    ParkingAssignmentCommand,
    ParkingSpotDisplayCommand,
    ExitAuthorizationCommand,
    ProblemMessage,
    VehicleMoveCommand,
    decode,
)

__all__ = [
    "Message",
    "decode",
    # events
    "OccupancyEvent",
    "GateMotionEvent",
    "NfcScanEvent",
    "DurationDialEvent",
    "DistanceEvent",
    # commands
    "GateCommand",
    "LotFullCommand",
    "BufferLedCommand",
    "VehicleMoveCommand",
    "ParkingAssignmentCommand",
    "ParkingSpotDisplayCommand",
    "ExitAuthorizationCommand",
    # planning
    "ProblemMessage",
    "PlanMessage",
    "AdmissionResult",
    # vocabulary
    "READER_GATE",
    "READER_CHECKOUT",
    "GATE_OPEN",
    "GATE_CLOSE",
]
