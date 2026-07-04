"""What every actuator driver looks like from the bus's point of view.

An actuator is a hardware *output*: it subscribes to a command topic from
`parking.common.models` and drives a device (gate motor, buffer LED, vehicle
move). Like sensors, the contract the system relies on is the command on the
topic, not this class - so the real drivers in `drivers.py` and the
`RecordingActuators` test double in `parking.simulation` are interchangeable.

An actuator is just a `Component`: it `start()`s (subscribing to its command
topic) and `stop()`s (releasing the device).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..common.component import Component


@runtime_checkable
class Actuator(Component, Protocol):
    """A device driver that consumes commands off the bus and acts on them."""
