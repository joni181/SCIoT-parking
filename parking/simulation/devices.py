"""Simulated sensors (publish events) and actuators (record commands).

`SimulatedSensors` is the development stand-in for the real drivers in
`parking.sensors` (`OccupancySensor`, `GateMotionSensor`, `NfcReader`,
`DurationDial`): instead of reading a device it publishes the exact same events.
It is a manual injector (one method per event) rather than a single `Sensor`, so
it deliberately does not implement that interface.

`RecordingActuators` is the test double for the drivers in `parking.actuators`
(`GateMotor`, `BufferLed`, `VehicleMover`): instead of moving hardware it records
the commands it receives so tests can assert on them and the demo can print them.
"""
from __future__ import annotations

from typing import List, Optional

from ..common import models as m
from ..common.messaging import MessageBus


class SimulatedSensors:
    """Publishes sensor events on demand, as if real hardware fired them."""

    def __init__(self, bus: MessageBus, source: str = "sim/pi/sensors") -> None:
        self._bus = bus
        self._source = source

    # --- light sensors at the parking / buffer spots -----------------------
    def car_parks(self, spot_id: str, raw_value: Optional[int] = None) -> None:
        self._bus.publish_message(
            m.OccupancyEvent(spot_id=spot_id, occupied=True, raw_value=raw_value, source=self._source)
        )

    def car_leaves(self, spot_id: str, raw_value: Optional[int] = None) -> None:
        self._bus.publish_message(
            m.OccupancyEvent(spot_id=spot_id, occupied=False, raw_value=raw_value, source=self._source)
        )

    # --- motion sensor at the gate -----------------------------------------
    def car_arrives_at_gate(self) -> None:
        self._bus.publish_message(m.GateMotionEvent(present=True, source=self._source))

    def gate_clear(self) -> None:
        self._bus.publish_message(m.GateMotionEvent(present=False, source=self._source))

    # --- NFC readers (gate + checkout) -------------------------------------
    def scan_nfc(self, uid: str, reader: str = m.READER_GATE) -> None:
        self._bus.publish_message(m.NfcScanEvent(uid=uid, reader=reader, source=self._source))

    # --- rotary dial (expected parking duration) ---------------------------
    def turn_dial(self, minutes: int, raw_value: int = 0) -> None:
        self._bus.publish_message(
            m.DurationDialEvent(raw_value=raw_value, minutes=minutes, source=self._source)
        )


class RecordingActuators:
    """Subscribes to actuator commands and records them (no hardware)."""

    def __init__(self, bus: MessageBus) -> None:
        self.gate_commands: List[m.GateCommand] = []
        self.led_commands: List[m.BufferLedCommand] = []
        self.vehicle_moves: List[m.VehicleMoveCommand] = []

        bus.subscribe_message(m.GateCommand.TOPIC, self.gate_commands.append)
        bus.subscribe_message(m.BufferLedCommand.TOPIC, self.led_commands.append)
        bus.subscribe_message(m.VehicleMoveCommand.TOPIC, self.vehicle_moves.append)

    @property
    def gate_state(self) -> Optional[str]:
        """Last gate action seen (GATE_OPEN / GATE_CLOSE), or None."""
        return self.gate_commands[-1].action if self.gate_commands else None
