"""Real actuator drivers for the Raspberry Pi (skeletons).

Each class is the hardware counterpart of one channel that `RecordingActuators`
records in `parking.simulation`: where the test double just stores the command,
these subscribe to the same command topic and drive a device. Subscription
happens in `start()` (not `__init__`), so importing the package wires nothing
and the test suite never touches the GPIO. Each implements `Actuator`.

Hardware spikes for reference: experiments/led-blink-grove-pi.py (LED). The
gate actuator is a servo motor.
"""
from __future__ import annotations

from typing import Optional

from ..common import models as m
from ..common.messaging import MessageBus
from ..mega_link import MegaLink
from .base import Actuator


class GateServo(Actuator):
    """Servo motor at the gate. Consumes `GateCommand` (open / close).

    Drives the Mega's servo by sending "GATE OPEN" / "GATE CLOSE" over the
    shared `MegaLink` (see `hardware/mega/firmware/rotary_lcd_bringup/mega_controller.c`).
    With no `link` (simulated/no-hardware runs) this is a no-op, matching the
    previous skeleton behavior.
    """

    def __init__(self, bus: MessageBus, link: Optional[MegaLink] = None, source: str = "pi/actuator/gate") -> None:
        self._bus = bus
        self._link = link
        self._source = source

    def start(self) -> None:
        self._bus.subscribe_message(m.GateCommand.TOPIC, self._on_command)

    def stop(self) -> None:
        ...

    def _on_command(self, msg: m.GateCommand) -> None:
        if self._link is None:
            return
        self._link.send("GATE OPEN" if msg.action == m.GATE_OPEN else "GATE CLOSE")


class BufferLed(Actuator):
    """Buffer-slot indicator LED. Consumes `BufferLedCommand` (on / off)."""

    def __init__(self, bus: MessageBus, source: str = "pi/actuator/led") -> None:
        self._bus = bus
        self._source = source

    def start(self) -> None:
        self._bus.subscribe_message(m.BufferLedCommand.TOPIC, self._on_command)
        self._bus.subscribe_message(m.ParkingSpotDisplayCommand.TOPIC, self._on_spot_display)

    def stop(self) -> None:
        # TODO: turn the LED off / release the pin.
        ...

    def _on_command(self, msg: m.BufferLedCommand) -> None:
        # TODO: set the LED for msg.slot_id to msg.on.
        ...

    def _on_spot_display(self, msg: m.ParkingSpotDisplayCommand) -> None:
        # TODO: show msg.spot_id using the available LEDs/display hardware.
        ...


# Compatibility for existing imports while the project transitions terminology.
GateMotor = GateServo


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
