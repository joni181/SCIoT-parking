"""Time- and distance-based safety closure for the planner-authorized servo gate.

There is no gate motion sensor in the current hardware (see `hardware/pinmap.yaml`),
so closing can't be reactive to "a vehicle passed through." Instead: a
`GateCommand(open)` starts a fixed delay, after which the gate closes -
unless the ultrasonic ranger still reports something within `clear_distance_cm`
of the gate, in which case it keeps waiting for a distance reading past that
before closing.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from ..common import models as m
from ..common.messaging import MessageBus

TimerFactory = Callable[[float, Callable[[], None]], threading.Timer]


class GateSafetyController:
    """Auto-close an opened gate after a delay, held open while something is near."""

    def __init__(
        self,
        bus: MessageBus,
        close_delay_s: float = 5.0,
        clear_distance_cm: float = 8.0,
        source: str = "gate_safety",
        timer_factory: TimerFactory = threading.Timer,
    ) -> None:
        self._bus = bus
        self._close_delay_s = close_delay_s
        self._clear_distance_cm = clear_distance_cm
        self._source = source
        self._timer_factory = timer_factory
        self._lock = threading.Lock()
        self._open = False
        self._delay_elapsed = False
        self._latest_distance_cm: Optional[float] = None
        self._timer: Optional[threading.Timer] = None

    def start(self) -> None:
        self._bus.subscribe_message(m.GateCommand.TOPIC, self._on_gate_command)
        self._bus.subscribe_message(m.DistanceEvent.TOPIC, self._on_distance)

    def stop(self) -> None:
        with self._lock:
            self._cancel_timer_locked()

    def _on_gate_command(self, msg: m.GateCommand) -> None:
        with self._lock:
            if msg.action == m.GATE_OPEN:
                self._open = True
                self._delay_elapsed = False
                self._cancel_timer_locked()
                self._timer = self._timer_factory(self._close_delay_s, self._on_delay_elapsed)
                self._timer.daemon = True
                self._timer.start()
            elif msg.action == m.GATE_CLOSE:
                self._open = False
                self._cancel_timer_locked()

    def _on_delay_elapsed(self) -> None:
        with self._lock:
            self._timer = None
            self._delay_elapsed = True
            close_now = self._open and not self._is_blocked_locked()
            if close_now:
                self._open = False
        if close_now:
            self._publish_close()

    def _on_distance(self, msg: m.DistanceEvent) -> None:
        with self._lock:
            self._latest_distance_cm = msg.distance_cm
            close_now = self._open and self._delay_elapsed and not self._is_blocked_locked()
            if close_now:
                self._open = False
        if close_now:
            self._publish_close()

    def _is_blocked_locked(self) -> bool:
        return self._latest_distance_cm is not None and self._latest_distance_cm < self._clear_distance_cm

    def _cancel_timer_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _publish_close(self) -> None:
        self._bus.publish_message(m.GateCommand(action=m.GATE_CLOSE, source=self._source))
