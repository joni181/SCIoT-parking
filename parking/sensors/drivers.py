"""Real sensor drivers for the Raspberry Pi (skeletons).

Each class here is the hardware counterpart of a `SimulatedSensors` method in
`parking.simulation`: where the simulation calls `bus.publish_message(...)`
directly, these read a Grove/RC522 device and publish the *same* event. The
wiring spikes in `experiments/*.py` show the raw device access; the `TODO`s mark
exactly where that code drops in.

Until the hardware code is filled in these are inert: constructing one wires
nothing and `start()`/`stop()` are safe no-ops, so importing the package and
running the test suite never touches the GPIO. Each implements `Sensor`.
"""
from __future__ import annotations

from typing import Optional

from ..common import models as m
from ..common.messaging import MessageBus
from .base import Sensor


class OccupancySensor(Sensor):
    """Light sensor over one parking/buffer spot -> `OccupancyEvent`.

    Raw Grove read: see experiments/light-sensor-grove-pi.py.
    """

    def __init__(self, bus: MessageBus, spot_id: str, source: str = "pi/sensor/light") -> None:
        self._bus = bus
        self._spot_id = spot_id
        self._source = f"{source}/{spot_id}"

    def start(self) -> None:
        # TODO: poll the Grove light pin (or wire an interrupt) and call
        #       self._publish(occupied=...) whenever the reading crosses the
        #       occupied/free threshold.
        ...

    def stop(self) -> None:
        # TODO: stop the poll loop / release the GPIO handle.
        ...

    def _publish(self, occupied: bool, raw_value: Optional[int] = None) -> None:
        self._bus.publish_message(
            m.OccupancyEvent(
                spot_id=self._spot_id, occupied=occupied, raw_value=raw_value, source=self._source
            )
        )


class GateMotionSensor(Sensor):
    """Motion sensor at the gate -> `GateMotionEvent`.

    Raw Grove read: see experiments/motion-sensor-grove-pi.py.
    """

    def __init__(self, bus: MessageBus, source: str = "pi/sensor/motion/gate") -> None:
        self._bus = bus
        self._source = source

    def start(self) -> None:
        # TODO: poll/interrupt the Grove motion pin; call self._publish(present).
        ...

    def stop(self) -> None:
        ...

    def _publish(self, present: bool) -> None:
        self._bus.publish_message(m.GateMotionEvent(present=present, source=self._source))


class NfcReader(Sensor):
    """RC522 NFC reader at the gate or checkout -> `NfcScanEvent`.

    Raw read: see experiments/mfrc522.py / experiments/test-rfid.py.
    """

    def __init__(self, bus: MessageBus, reader: str = m.READER_GATE, source: str = "pi/sensor/nfc") -> None:
        self._bus = bus
        self._reader = reader
        self._source = f"{source}/{reader}"

    def start(self) -> None:
        # TODO: loop on RC522 reads; on a successful scan call self._publish(uid).
        ...

    def stop(self) -> None:
        ...

    def _publish(self, uid: str) -> None:
        self._bus.publish_message(m.NfcScanEvent(uid=uid, reader=self._reader, source=self._source))


class DurationDial(Sensor):
    """Rotary-angle dial for expected parking duration -> `DurationDialEvent`.

    Raw Grove read: see experiments/rotary-sensor-grove-pi.py.
    """

    def __init__(self, bus: MessageBus, source: str = "pi/sensor/rotary") -> None:
        self._bus = bus
        self._source = source

    def start(self) -> None:
        # TODO: poll the rotary angle pin; map the raw value to minutes and call
        #       self._publish(raw_value, minutes) when the dial settles.
        ...

    def stop(self) -> None:
        ...

    def _publish(self, raw_value: int, minutes: Optional[int] = None) -> None:
        self._bus.publish_message(
            m.DurationDialEvent(raw_value=raw_value, minutes=minutes, source=self._source)
        )
