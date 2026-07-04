"""Bus adapter that regenerates a planning problem after state changes."""
from __future__ import annotations

from ..common import models as m
from ..common.messaging import MessageBus
from ..storage.base import StateStore
from .base import ProblemGenerator


class ProblemGenerationService:
    def __init__(self, bus: MessageBus, store: StateStore, generator: ProblemGenerator) -> None:
        self._bus = bus
        self._store = store
        self._generator = generator

    def start(self) -> None:
        for topic in (
            m.OccupancyEvent.TOPIC,
            m.NfcScanEvent.TOPIC,
            m.DurationDialEvent.TOPIC,
            m.VehicleMoveCommand.TOPIC,
        ):
            self._bus.subscribe_message(topic, self._on_state_change)

    def stop(self) -> None:
        ...

    def generate_now(self) -> m.ProblemMessage:
        problem = self._generator.generate(self._store)
        self._bus.publish_message(problem)
        return problem

    def _on_state_change(self, _message: m.Message) -> None:
        self.generate_now()
