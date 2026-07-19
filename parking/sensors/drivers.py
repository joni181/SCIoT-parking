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
import time
from typing import Callable, Optional

from ..common import models as m
from ..common.messaging import MessageBus
from ..mega_link import MegaLink
from .base import Sensor


_LIGHT_LINE = re.compile(r"^LIGHT sensor=(?P<sensor>\S+) raw=(?P<raw>\d+)$")


class OccupancySensor(Sensor):
    """Photoresistor over one parking/buffer spot -> `OccupancyEvent`.

    The Mega firmware (`hardware/mega/firmware/mega_controller/mega_controller.c`)
    prints one `LIGHT sensor=<label> raw=<0-1023>` line per photoresistor
    (`photoresistor_a15`=buffer B1, `photoresistor_a12/a13/a14`=P1/P2/P3)
    roughly twice a second. `sensor_label` picks which one this instance
    listens for - every `OccupancySensor` sees every `LIGHT` line over the
    shared `MegaLink`, so this filter is what keeps spots from reading each
    other's sensor.

    `threshold`/`occupied_below_threshold` need calibrating per sensor against
    its actual mounting: whether a lower or higher raw ADC value means
    "something is blocking the light" depends on which way that spot's LDR
    voltage divider is wired (see pinmap.yaml's wiring note), and the exact
    crossover point depends on ambient light and the mounting position - they
    are not expected to be the same across spots. Watch a few `LIGHT ...`
    readings for the specific sensor with the spot empty vs. covered (see
    `hardware/pi/bringup/test_photoresistor_threshold.py`) and set both to
    match what you actually observe.

    Only publishes when `occupied` actually flips, not on every ~0.5s
    reading: downstream, every `OccupancyEvent` triggers a full replan
    (`ProblemGenerationService`), so republishing an unchanged state floods
    the bus with redundant replans - and if a car is mid-admission, a burst
    of near-simultaneous replans can each independently re-derive the same
    `open-entry` action before the first one's result has propagated back,
    which looks like the gate re-opening/closing on its own.
    """

    def __init__(
        self,
        bus: MessageBus,
        spot_id: str,
        link: Optional[MegaLink] = None,
        sensor_label: str = "photoresistor_a15",
        threshold: int = 512,
        occupied_below_threshold: bool = True,
        source: str = "pi/sensor/light",
    ) -> None:
        self._bus = bus
        self._spot_id = spot_id
        self._link = link
        self._sensor_label = sensor_label
        self._threshold = threshold
        self._occupied_below_threshold = occupied_below_threshold
        self._source = f"{source}/{spot_id}"
        self._last_occupied: Optional[bool] = None

    def start(self) -> None:
        if self._link is not None:
            self._link.add_listener(self._on_line)

    def stop(self) -> None:
        if self._link is not None:
            self._link.remove_listener(self._on_line)

    def _on_line(self, line: str) -> None:
        match = _LIGHT_LINE.match(line)
        if not match or match.group("sensor") != self._sensor_label:
            return
        raw = int(match.group("raw"))
        below = raw < self._threshold
        occupied = below if self._occupied_below_threshold else not below
        if occupied == self._last_occupied:
            return
        self._last_occupied = occupied
        self._publish(occupied=occupied, raw_value=raw)

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

    The firmware itself tries not to repeat a still-present card, but its
    anti-collision read can intermittently miss it for one poll even while the
    card hasn't moved, which resets its own "already saw this card" tracking
    and republishes. A card held a bit longer than a quick tap can therefore
    produce several `NFC reader=... uid=...` lines for what is physically one
    scan. Debounce here: don't republish the same UID again within
    `debounce_s` of the last publish, so downstream (which treats every scan
    as a fresh arrival/checkout request) doesn't re-run for the same tap.
    """

    def __init__(
        self,
        bus: MessageBus,
        link: Optional[MegaLink] = None,
        reader: str = m.READER_GATE,
        firmware_reader: int = 1,
        source: str = "pi/sensor/nfc",
        debounce_s: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bus = bus
        self._link = link
        self._reader = reader
        self._firmware_reader = firmware_reader
        self._source = f"{source}/{reader}"
        self._debounce_s = debounce_s
        self._clock = clock
        self._last_uid: Optional[str] = None
        self._last_scan_time: Optional[float] = None

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
        uid = match.group("uid")
        now = self._clock()
        if (
            uid == self._last_uid
            and self._last_scan_time is not None
            and (now - self._last_scan_time) < self._debounce_s
        ):
            return
        self._last_uid = uid
        self._last_scan_time = now
        self._publish(uid)

    def _publish(self, uid: str) -> None:
        self._bus.publish_message(m.NfcScanEvent(uid=uid, reader=self._reader, source=self._source))


_ROTARY_LINE = re.compile(r"^ROTARY ticks=(?P<ticks>-?\d+)$")


class DurationDial(Sensor):
    """Rotary encoder -> `DurationDialEvent` (expected parking duration).

    The Mega firmware (`hardware/mega/firmware/mega_controller/mega_controller.c`)
    emits `ROTARY ticks=<signed n>` once per detent - `ticks` is an unbounded
    count relative to boot (not an absolute angle; the encoder has no home
    position). Each tick shifts the selected duration by `minutes_per_tick`
    away from `default_minutes`, clamped to [`min_minutes`, `max_minutes`].
    `parking.problem_generation.PddlProblemGenerator` only cares about whole
    hours (`expected_minutes // 60`) for spot selection, so exact granularity
    isn't critical - the defaults just need to feel reasonable to turn.
    """

    def __init__(
        self,
        bus: MessageBus,
        link: Optional[MegaLink] = None,
        default_minutes: int = 30,
        minutes_per_tick: int = -5,  # negative: physical rotation direction is reversed
        min_minutes: int = 5,
        max_minutes: int = 180,
        source: str = "pi/sensor/rotary",
    ) -> None:
        self._bus = bus
        self._link = link
        self._default_minutes = default_minutes
        self._minutes_per_tick = minutes_per_tick
        self._min_minutes = min_minutes
        self._max_minutes = max_minutes
        self._source = source

    def start(self) -> None:
        if self._link is not None:
            self._link.add_listener(self._on_line)

    def stop(self) -> None:
        if self._link is not None:
            self._link.remove_listener(self._on_line)

    def _on_line(self, line: str) -> None:
        match = _ROTARY_LINE.match(line)
        if not match:
            return
        ticks = int(match.group("ticks"))
        minutes = self._default_minutes + ticks * self._minutes_per_tick
        minutes = max(self._min_minutes, min(self._max_minutes, minutes))
        self._publish(raw_value=ticks, minutes=minutes)

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
