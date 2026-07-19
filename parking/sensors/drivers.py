"""Real sensor drivers for the Raspberry Pi (skeletons).

Each class here is the hardware counterpart of a `SimulatedSensors` method in
`parking.simulation`: where the simulation calls `bus.publish_message(...)`
directly, these read a Grove/RC522 device and publish the *same* event. The
wiring spikes in `experiments/*.py` show the raw device access; the `TODO`s mark
exactly where that code drops in.

Until the hardware code is filled in these are inert: constructing one wires
nothing and `start()`/`stop()` are safe no-ops, so importing the package and
running the test suite never touches the GPIO. Each implements `Sensor`.

`DistanceSensor` and `NfcReader` read the Mega over its shared `MegaLink`
(see `parking.mega_link`) rather than opening their own serial port, since
both the distance ranger and the NFC readers are multiplexed onto the same
USB-serial connection.
"""
from __future__ import annotations

import re
from typing import Optional

from ..common import models as m
from ..common.messaging import MessageBus
from ..mega_link import MegaLink
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


_NFC_LINE = re.compile(r"^NFC reader=(?P<reader>\d) uid=(?P<uid>[0-9A-Fa-f]+)$")


class NfcReader(Sensor):
    """RC522 NFC reader at the gate or checkout -> `NfcScanEvent`.

    The Mega firmware (`hardware/mega/firmware/mega_controller/mega_controller.c`)
    prints `NFC reader=<1|2> uid=<hex>` whenever a reader sees a (new) card.
    Reader 1 is the entrance/gate reader, reader 2 is the optional checkout
    reader; `firmware_reader` picks which one this instance listens for.
    """

    def __init__(
        self,
        bus: MessageBus,
        link: Optional[MegaLink] = None,
        reader: str = m.READER_GATE,
        firmware_reader: int = 1,
        source: str = "pi/sensor/nfc",
    ) -> None:
        self._bus = bus
        self._link = link
        self._reader = reader
        self._firmware_reader = firmware_reader
        self._source = f"{source}/{reader}"

    def start(self) -> None:
        if self._link is not None:
            self._link.add_listener(self._on_line)

    def stop(self) -> None:
        if self._link is not None:
            self._link.remove_listener(self._on_line)

    def _on_line(self, line: str) -> None:
        match = _NFC_LINE.match(line)
        if not match or int(match.group("reader")) != self._firmware_reader:
            return
        self._publish(match.group("uid"))

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


_DISTANCE_LINE = re.compile(r"^DISTANCE sensor=\S+ (?:cm=(?P<cm>-?\d+)|status=(?P<status>\S+))")


class DistanceSensor(Sensor):
    """HC-SR04P ultrasonic ranger -> `DistanceEvent`.

    The Mega firmware (`hardware/mega/firmware/mega_controller/mega_controller.c`)
    prints one line per reading over its USB-serial connection, e.g.
    `DISTANCE sensor=hc_sr04p_d7_d24 cm=42` or `... status=out-of-range`. This
    driver listens on the shared `MegaLink`, parses those lines, and
    republishes each reading as a `DistanceEvent` (`distance_cm=None` when out
    of range).
    """

    def __init__(self, bus: MessageBus, link: MegaLink, source: str = "pi/sensor/distance") -> None:
        self._bus = bus
        self._link = link
        self._source = source

    def start(self) -> None:
        self._link.add_listener(self._on_line)

    def stop(self) -> None:
        self._link.remove_listener(self._on_line)

    def _on_line(self, line: str) -> None:
        match = _DISTANCE_LINE.match(line)
        if not match:
            return
        cm = match.group("cm")
        self._publish(float(cm) if cm is not None else None)

    def _publish(self, distance_cm: Optional[float]) -> None:
        self._bus.publish_message(m.DistanceEvent(distance_cm=distance_cm, source=self._source))
