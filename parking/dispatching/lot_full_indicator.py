"""Status-LED indicator for "every parking spot is occupied" (Raspberry Pi).

Watches `OccupancyEvent` for the configured parking spots (not the buffer)
and publishes `LotFullCommand` only when the all-occupied state actually
flips, so `parking.actuators.StatusLed` doesn't get flooded with redundant
commands on every reading. Runs entirely on the Pi: `OccupancyEvent`
originates locally from `OccupancySensor`, and the LED it drives is also
local, so this loop doesn't depend on the broker/laptop being reachable.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

from ..common import models as m
from ..common.messaging import MessageBus


class LotFullIndicator:
    """Publishes `LotFullCommand(full=...)` when occupancy of every
    configured parking spot changes, all-occupied or not."""

    def __init__(self, bus: MessageBus, parking_spots: Sequence[str], source: str = "lot_full_indicator") -> None:
        self._bus = bus
        self._source = source
        self._occupied: Dict[str, bool] = {spot: False for spot in parking_spots}
        self._last_full: Optional[bool] = None

    def start(self) -> None:
        self._bus.subscribe_message(m.OccupancyEvent.TOPIC, self._on_occupancy)

    def stop(self) -> None:
        ...

    def _on_occupancy(self, msg: m.OccupancyEvent) -> None:
        if msg.spot_id not in self._occupied:
            return
        self._occupied[msg.spot_id] = msg.occupied
        full = all(self._occupied.values())
        if full == self._last_full:
            return
        self._last_full = full
        self._bus.publish_message(m.LotFullCommand(full=full, source=self._source))
