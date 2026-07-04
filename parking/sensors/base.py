"""What every sensor driver looks like from the bus's point of view.

A sensor is a hardware *input*: it reads a device (light, motion, NFC, rotary
dial) and publishes the matching event from `parking.common.models`. It never
calls another module directly - storage, visualization and problem generation
simply subscribe to the events it emits.

The interface is deliberately tiny: a sensor is just a `Component`. It
`start()`s a read/poll loop and `stop()`s it; *which* event it publishes is the
driver's own business. The contract the rest of the system depends on is the
event on the topic, not this class - which is exactly why the real Grove/RC522
drivers in `drivers.py` and the `SimulatedSensors` test harness in
`parking.simulation` are interchangeable.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..common.component import Component


@runtime_checkable
class Sensor(Component, Protocol):
    """A hardware input that publishes events onto the bus.

    Real implementations live in `drivers.py`. The simulation's
    `SimulatedSensors` plays the same role in tests by injecting the identical
    events with no hardware attached.
    """
