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
    DurationDialEvent,
    GateCommand,
    GateMotionEvent,
    Message,
    NfcScanEvent,
    OccupancyEvent,
    PlanMessage,
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
    # commands
    "GateCommand",
    "BufferLedCommand",
    "VehicleMoveCommand",
    # planning
    "ProblemMessage",
    "PlanMessage",
    # vocabulary
    "READER_GATE",
    "READER_CHECKOUT",
    "GATE_OPEN",
    "GATE_CLOSE",
]
