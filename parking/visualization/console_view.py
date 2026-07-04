"""Console parking-lot view (skeleton).

The simplest `View`: subscribe to occupancy events and print the lot state. It
keeps its own tiny copy of occupancy (a view never reaches into control logic or
storage internals). A richer GUI view would implement the same `View` interface.
"""
from __future__ import annotations

from typing import Dict

from ..common import models as m
from ..common.messaging import MessageBus
from .base import View


class ConsoleLotView(View):
    """Print parking-lot occupancy as it changes on the bus."""

    def __init__(self, bus: MessageBus) -> None:
        self._bus = bus
        self._occupied: Dict[str, bool] = {}

    def start(self) -> None:
        self._bus.subscribe_message(m.OccupancyEvent.TOPIC, self._on_occupancy)

    def stop(self) -> None:
        ...

    def _on_occupancy(self, msg: m.OccupancyEvent) -> None:
        self._occupied[msg.spot_id] = msg.occupied
        self.render()

    def render(self) -> None:
        # TODO: replace with a real lot layout / GUI. For now, a one-line dump.
        cells = " ".join(f"{spot}:{'X' if occ else '.'}" for spot, occ in sorted(self._occupied.items()))
        print(f"[lot] {cells}")
