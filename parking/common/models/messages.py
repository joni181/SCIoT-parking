"""Message schemas exchanged over the bus.

Every message is a small dataclass that knows two things: the ``TOPIC`` it
belongs on and a ``TYPE`` discriminator. On the wire a message is a JSON
*envelope*::

    {
      "type":   "occupancy",          # which dataclass
      "ts":     1719500000.0,         # unix timestamp (set at creation)
      "source": "pi/sensor/light/P1", # who sent it (tracing/debug)
      "data":   { ... }               # the type-specific fields
    }

`encode()` turns a dataclass into envelope bytes; `decode()` turns received
bytes back into the right dataclass via the type registry. Keeping the contract
here (and only here) means the Pi and the laptop can never disagree about the
shape of a message.

No third-party dependencies: stdlib dataclasses + json only.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, Dict, List, Optional, Type

from .. import topics

# --- small vocabulary shared across messages -------------------------------
READER_GATE = "gate"          # NFC reader at the entrance gate
READER_CHECKOUT = "checkout"  # NFC reader at the supermarket register

GATE_OPEN = "open"
GATE_CLOSE = "close"


# --- envelope plumbing ------------------------------------------------------
_REGISTRY: Dict[str, Type["Message"]] = {}


def _register(cls: Type["Message"]) -> Type["Message"]:
    """Class decorator: make a message type decodable by its TYPE string."""
    if not cls.TYPE:
        raise ValueError(f"{cls.__name__} must set a non-empty TYPE")
    _REGISTRY[cls.TYPE] = cls
    return cls


@dataclass
class Message:
    """Base class for everything on the bus.

    Subclasses set the class vars ``TYPE`` and ``TOPIC`` and add their own data
    fields (all with defaults, so dataclass inheritance stays happy). The
    common envelope fields ``source`` and ``ts`` live here.
    """

    TYPE: ClassVar[str] = ""
    TOPIC: ClassVar[str] = ""

    source: str = ""
    ts: float = field(default_factory=time.time)

    def data(self) -> Dict[str, Any]:
        """The type-specific payload (everything except the envelope fields)."""
        envelope = {"source", "ts"}
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name not in envelope}

    def to_envelope(self) -> Dict[str, Any]:
        return {"type": self.TYPE, "ts": self.ts, "source": self.source, "data": self.data()}

    def encode(self) -> bytes:
        return json.dumps(self.to_envelope()).encode("utf-8")

    @classmethod
    def from_envelope(cls, env: Dict[str, Any]) -> "Message":
        target = _REGISTRY.get(env.get("type"))
        if target is None:
            raise ValueError(f"unknown message type: {env.get('type')!r}")
        return target(source=env.get("source", ""), ts=env.get("ts", time.time()), **env.get("data", {}))


def decode(raw: bytes | str) -> Message:
    """Turn received bytes/str into the concrete Message subclass."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return Message.from_envelope(json.loads(raw))


# ===========================================================================
# Events - published by sensors on the Pi.
# ===========================================================================
@_register
@dataclass
class OccupancyEvent(Message):
    """A parking or buffer spot became occupied / free (light sensor)."""

    TYPE = "occupancy"
    TOPIC = topics.EVT_OCCUPANCY

    spot_id: str = ""
    occupied: bool = False
    raw_value: Optional[int] = None  # raw sensor reading, for debugging/tuning


@_register
@dataclass
class GateMotionEvent(Message):
    """A vehicle is present (or no longer present) at the gate (motion sensor)."""

    TYPE = "gate_motion"
    TOPIC = topics.EVT_GATE_MOTION

    present: bool = False


@_register
@dataclass
class NfcScanEvent(Message):
    """A customer card was scanned at one of the NFC readers."""

    TYPE = "nfc_scan"
    TOPIC = topics.EVT_NFC_SCAN

    uid: str = ""
    reader: str = READER_GATE  # READER_GATE or READER_CHECKOUT


@_register
@dataclass
class DurationDialEvent(Message):
    """The customer set their expected parking duration on the rotary dial."""

    TYPE = "duration_dial"
    TOPIC = topics.EVT_DURATION_DIAL

    raw_value: int = 0
    minutes: Optional[int] = None  # raw_value mapped to minutes (if interpreted)


# ===========================================================================
# Commands - published by control logic, consumed by actuators on the Pi.
# ===========================================================================
@_register
@dataclass
class GateCommand(Message):
    """Open or close the entrance gate (stepper motor)."""

    TYPE = "gate_cmd"
    TOPIC = topics.CMD_GATE

    action: str = GATE_OPEN  # GATE_OPEN or GATE_CLOSE


@_register
@dataclass
class BufferLedCommand(Message):
    """Turn a buffer-slot indicator LED on or off."""

    TYPE = "buffer_led_cmd"
    TOPIC = topics.CMD_BUFFER_LED

    slot_id: str = ""
    on: bool = False


@_register
@dataclass
class VehicleMoveCommand(Message):
    """Instruct the (human-simulated) move of a car between two spots."""

    TYPE = "vehicle_move_cmd"
    TOPIC = topics.CMD_VEHICLE_MOVE

    vehicle_uid: str = ""
    from_spot: str = ""
    to_spot: str = ""


# ===========================================================================
# Planning - laptop internal (problem generator -> planner -> dispatcher).
# ===========================================================================
@_register
@dataclass
class ProblemMessage(Message):
    """A generated PDDL problem instance, ready for the planner."""

    TYPE = "problem"
    TOPIC = topics.PLANNING_PROBLEM

    problem_id: str = ""
    pddl: str = ""


@_register
@dataclass
class PlanMessage(Message):
    """A solved plan for the dispatcher to execute.

    ``actions`` is an ordered list of ``{"name": str, "args": [...]}`` steps.
    """

    TYPE = "plan"
    TOPIC = topics.PLANNING_PLAN

    problem_id: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
