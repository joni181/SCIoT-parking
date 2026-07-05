"""Reactive safety closure for the planner-authorized servo gate."""
from __future__ import annotations

from ..common import models as m
from ..common.messaging import MessageBus


class GateSafetyController:
    """Close an opened gate after a vehicle was seen and then cleared it."""

    def __init__(self, bus: MessageBus, source: str = "gate_safety") -> None:
        self._bus = bus
        self._source = source
        self._open = False
        self._saw_vehicle = False
        self._present = False

    def start(self) -> None:
        self._bus.subscribe_message(m.GateCommand.TOPIC, self._on_gate_command)
        self._bus.subscribe_message(m.GateMotionEvent.TOPIC, self._on_motion)

    def stop(self) -> None:
        ...

    def _on_gate_command(self, msg: m.GateCommand) -> None:
        if msg.action == m.GATE_OPEN:
            self._open = True
            self._saw_vehicle = self._present
        elif msg.action == m.GATE_CLOSE:
            self._open = False
            self._saw_vehicle = False

    def _on_motion(self, msg: m.GateMotionEvent) -> None:
        self._present = msg.present
        if not self._open:
            return
        if msg.present:
            self._saw_vehicle = True
        elif self._saw_vehicle:
            self._open = False
            self._saw_vehicle = False
            self._bus.publish_message(m.GateCommand(action=m.GATE_CLOSE, source=self._source))
