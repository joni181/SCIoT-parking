"""Illustrative control / consumer logic that ties events to outcomes.

These exist so the end-to-end message flow runs *today* and the two driving
questions have a concrete answer. They are intentionally simple stand-ins that
already speak the real module interfaces (see `parking/<module>/base.py`):

  * `ReactiveGateController` is a `parking.common.Component`. It will eventually
    live in `dispatching/` - see docs/message-flow.md "Open decisions".
  * `OccupancyTracker` implements `parking.storage.OccupancyStore` (the
    occupancy slice of `StateStore`); it stands in for `storage/` + `viz/`.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from ..common import models as m
from ..common.component import Component
from ..common.messaging import MessageBus
from ..storage.base import OccupancyStore


class ReactiveGateController(Component):
    """Open the gate when a *recognised* car waits, close it once it passes.

    Answers: "a sensor tells the Pi a car is at the gate -> the gate opens."
    The gate only opens when BOTH conditions hold: motion present at the gate
    AND a known card was scanned at the gate reader.

    Implements `parking.common.Component`; it wires its subscriptions in
    `__init__`, so `start()`/`stop()` are no-ops.
    """

    def __init__(
        self,
        bus: MessageBus,
        known_uids: Optional[Iterable[str]] = None,
        source: str = "sim/controller/gate",
    ) -> None:
        self._bus = bus
        self._known = set(known_uids or [])
        self._source = source
        self._car_present = False
        self._authorized = False

        bus.subscribe_message(m.GateMotionEvent.TOPIC, self._on_motion)
        bus.subscribe_message(m.NfcScanEvent.TOPIC, self._on_nfc)

    def start(self) -> None:  # subscriptions are wired in __init__
        ...

    def stop(self) -> None:
        ...

    def authorize(self, uid: str) -> None:
        """Register a card UID as a known/registered customer."""
        self._known.add(uid)

    def _on_motion(self, msg: m.GateMotionEvent) -> None:
        self._car_present = msg.present
        if not msg.present:
            # Car has driven through: reset and close behind it.
            self._authorized = False
            self._bus.publish_message(m.GateCommand(action=m.GATE_CLOSE, source=self._source))
        else:
            self._maybe_open()

    def _on_nfc(self, msg: m.NfcScanEvent) -> None:
        if msg.reader != m.READER_GATE:
            return  # checkout scans are not our concern
        self._authorized = msg.uid in self._known
        self._maybe_open()

    def _maybe_open(self) -> None:
        if self._car_present and self._authorized:
            self._bus.publish_message(m.GateCommand(action=m.GATE_OPEN, source=self._source))


class OccupancyTracker(OccupancyStore):
    """Maintain spot occupancy from events - stand-in for storage + viz.

    Answers: "a light sensor on the Pi tells the laptop spot P1 is taken."
    Implements `parking.storage.OccupancyStore`, so the real storage module is a
    drop-in replacement for it.
    """

    def __init__(self, bus: MessageBus) -> None:
        self.occupied: Dict[str, bool] = {}
        bus.subscribe_message(m.OccupancyEvent.TOPIC, self._on_occupancy)

    def _on_occupancy(self, msg: m.OccupancyEvent) -> None:
        self.set_occupancy(msg.spot_id, msg.occupied)

    # --- OccupancyStore ----------------------------------------------------
    def is_occupied(self, spot_id: str) -> bool:
        return self.occupied.get(spot_id, False)

    def set_occupancy(self, spot_id: str, occupied: bool) -> None:
        self.occupied[spot_id] = occupied

    def free_spots(self, all_spots: Iterable[str]) -> List[str]:
        return [s for s in all_spots if not self.occupied.get(s, False)]
