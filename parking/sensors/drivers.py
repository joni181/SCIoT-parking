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

import re
import threading
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


_DISTANCE_LINE = re.compile(r"^DISTANCE sensor=\S+ (?:cm=(?P<cm>-?\d+)|status=(?P<status>\S+))")


class DistanceSensor(Sensor):
    """HC-SR04P ultrasonic ranger -> `DistanceEvent`.

    The Mega firmware (`hardware/mega/firmware/rotary_lcd_bringup/mega_controller.c`)
    prints one line per reading over its USB-serial connection, e.g.
    `DISTANCE sensor=hc_sr04p_d7_d24 cm=42` or `... status=out-of-range`. This
    driver owns that serial port, parses those lines on a background thread, and
    republishes each reading as a `DistanceEvent` (`distance_cm=None` when out of
    range).

    Requires `pyserial` (only listed in `requirements/pi.txt`); the import is
    deferred to `start()` so importing this module elsewhere stays hardware-free.
    """

    def __init__(
        self,
        bus: MessageBus,
        port: str = "/dev/ttyACM0",
        baudrate: int = 9600,
        source: str = "pi/sensor/distance",
    ) -> None:
        self._bus = bus
        self._port = port
        self._baudrate = baudrate
        self._source = source
        self._serial = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        import serial  # deferred: only required on the Pi with real hardware

        self._stop_event.clear()
        self._serial = serial.Serial(self._port, self._baudrate, timeout=1)
        self._thread = threading.Thread(target=self._run, name="distance-sensor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            raw = self._serial.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            match = _DISTANCE_LINE.match(raw)
            if not match:
                continue
            cm = match.group("cm")
            self._publish(float(cm) if cm is not None else None)

    def _publish(self, distance_cm: Optional[float]) -> None:
        self._bus.publish_message(m.DistanceEvent(distance_cm=distance_cm, source=self._source))
