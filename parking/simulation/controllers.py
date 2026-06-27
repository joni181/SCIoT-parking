"""Illustrative control / consumer logic that ties events to outcomes.

These exist so the end-to-end message flow runs *today* and the two driving
questions have a concrete answer. They are intentionally simple stand-ins:

  * `ReactiveGateController` will eventually live in `dispatching/` (and/or the
    planner) - see docs/message-flow.md "Open decisions".
  * `OccupancyTracker` is a stand-in for `storage/` + `visualization/`.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from ..common import models as m
from ..common.messaging import MessageBus


class ReactiveGateController:
    """Open the gate when a *recognised* car waits, close it once it passes.

    Answers: "a sensor tells the Pi a car is at the gate -> the gate opens."
    The gate only opens when BOTH conditions hold: motion present at the gate
    AND a known card was scanned at the gate reader.
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


class OccupancyTracker:
    """Maintain spot occupancy from events - stand-in for storage + viz.

    Answers: "a light sensor on the Pi tells the laptop spot P1 is taken."
    """

    def __init__(self, bus: MessageBus) -> None:
        self.occupied: Dict[str, bool] = {}
        bus.subscribe_message(m.OccupancyEvent.TOPIC, self._on_occupancy)

    def _on_occupancy(self, msg: m.OccupancyEvent) -> None:
        self.occupied[msg.spot_id] = msg.occupied

    def is_occupied(self, spot_id: str) -> bool:
        return self.occupied.get(spot_id, False)

    def free_spots(self, all_spots: Iterable[str]) -> List[str]:
        return [s for s in all_spots if not self.occupied.get(s, False)]
