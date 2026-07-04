"""Real actuator drivers for the Raspberry Pi (skeletons).

Each class is the hardware counterpart of one channel that `RecordingActuators`
records in `parking.simulation`: where the test double just stores the command,
these subscribe to the same command topic and drive a device. Subscription
happens in `start()` (not `__init__`), so importing the package wires nothing
and the test suite never touches the GPIO. Each implements `Actuator`.

Hardware spikes for reference: experiments/led-blink-grove-pi.py (LED), and the
stepper-motor wiring for the gate (TODO).
"""
from __future__ import annotations

from ..common import models as m
from ..common.messaging import MessageBus
from .base import Actuator


class GateMotor(Actuator):
    """Stepper motor at the gate. Consumes `GateCommand` (open / close)."""

    def __init__(self, bus: MessageBus, source: str = "pi/actuator/gate") -> None:
        self._bus = bus
        self._source = source

    def start(self) -> None:
        self._bus.subscribe_message(m.GateCommand.TOPIC, self._on_command)

    def stop(self) -> None:
        # TODO: de-energize / release the stepper.
        ...

    def _on_command(self, msg: m.GateCommand) -> None:
        # TODO: drive the stepper open or closed based on msg.action
        #       (m.GATE_OPEN / m.GATE_CLOSE).
        ...


class BufferLed(Actuator):
    """Buffer-slot indicator LED. Consumes `BufferLedCommand` (on / off)."""

    def __init__(self, bus: MessageBus, source: str = "pi/actuator/led") -> None:
        self._bus = bus
        self._source = source

    def start(self) -> None:
        self._bus.subscribe_message(m.BufferLedCommand.TOPIC, self._on_command)

    def stop(self) -> None:
        # TODO: turn the LED off / release the pin.
        ...

    def _on_command(self, msg: m.BufferLedCommand) -> None:
        # TODO: set the LED for msg.slot_id to msg.on.
        ...


class VehicleMover(Actuator):
    """The car move itself. Consumes `VehicleMoveCommand`.

    In the demo this is human-simulated: a person drives the car from
    `from_spot` to `to_spot`. A real valet/robot driver would slot in here.
    """

    def __init__(self, bus: MessageBus, source: str = "pi/actuator/vehicle") -> None:
        self._bus = bus
        self._source = source

    def start(self) -> None:
        self._bus.subscribe_message(m.VehicleMoveCommand.TOPIC, self._on_command)

    def stop(self) -> None:
        ...

    def _on_command(self, msg: m.VehicleMoveCommand) -> None:
        # TODO: signal the move of msg.vehicle_uid from msg.from_spot to
        #       msg.to_spot (e.g. light a path / print an instruction).
        ...
