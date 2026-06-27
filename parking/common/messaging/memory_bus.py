"""In-process message bus - no broker, no network, fully synchronous.

`MemoryBus` delivers each published message to every matching subscriber
*immediately, on the calling thread*. That makes the entire message flow
testable without a Raspberry Pi or an MQTT broker, and keeps tests
deterministic (no sleeps, no races). It honours the same ``+``/``#`` wildcards
as the real broker, so code written against it behaves the same on MQTT.
"""
from __future__ import annotations

from typing import List, Tuple

from ..topics import topic_matches
from .bus import Handler, MessageBus


class MemoryBus(MessageBus):
    def __init__(self) -> None:
        self._subs: List[Tuple[str, Handler]] = []
        # Full publish history (topic, payload) - convenient for assertions.
        self.published: List[Tuple[str, bytes]] = []

    def publish(self, topic: str, payload: bytes | str) -> None:
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        self.published.append((topic, payload))
        # Iterate over a copy so a handler may (un)subscribe without surprises.
        for pattern, handler in list(self._subs):
            if topic_matches(pattern, topic):
                handler(topic, payload)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs.append((topic, handler))

    def clear_history(self) -> None:
        self.published.clear()
