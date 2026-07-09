"""Unit checks for scenario command synchronization."""
from __future__ import annotations

import threading

from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.simulation.guided_demo import MessageInbox, ScenarioCancelled


def test_message_inbox_waits_for_matching_command_and_consumes_it():
    bus = MemoryBus()
    inbox = MessageInbox(bus)  # type: ignore[arg-type]
    cancel = threading.Event()
    runnable = threading.Event()
    runnable.set()
    bus.publish_message(m.GateCommand(action=m.GATE_CLOSE))
    bus.publish_message(m.GateCommand(action=m.GATE_OPEN))

    result = inbox.wait_for(
        m.GateCommand, lambda command: command.action == m.GATE_OPEN,
        cancel, runnable, timeout=0.1,
    )

    assert result.action == m.GATE_OPEN


def test_message_inbox_honours_cancellation():
    bus = MemoryBus()
    inbox = MessageInbox(bus)  # type: ignore[arg-type]
    cancel = threading.Event()
    cancel.set()
    runnable = threading.Event()
    runnable.set()

    try:
        inbox.wait_for(m.GateCommand, lambda _command: True, cancel, runnable, timeout=0.1)
    except ScenarioCancelled:
        pass
    else:
        raise AssertionError("expected cancellation")

