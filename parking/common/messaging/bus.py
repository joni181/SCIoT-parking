"""The message bus abstraction.

Every module talks to *a* ``MessageBus``, never to a concrete transport. That
single seam is what lets us:

  * run the real distributed system over MQTT (`MqttBus`), and
  * run the whole message flow in one process, with no broker and no hardware,
    for deterministic tests and simulations (`MemoryBus`).

The base class is transport-only (it moves ``(topic, bytes)``). The typed
convenience methods (`publish_message` / `subscribe_message`) bridge to the
`parking.common.models` dataclasses, with a lazy import so the transport layer
keeps no hard dependency on the schemas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # avoid import cycle at runtime
    from ..models import Message

# A raw handler is called with the concrete topic and the payload bytes.
Handler = Callable[[str, bytes], None]


class MessageBus(ABC):
    """Minimal publish/subscribe transport."""

    @abstractmethod
    def publish(self, topic: str, payload: bytes | str) -> None:
        """Publish ``payload`` to ``topic``."""

    @abstractmethod
    def subscribe(self, topic: str, handler: Handler) -> None:
        """Register ``handler`` for messages on ``topic`` (``+``/``#`` allowed)."""

    def start(self) -> None:
        """Begin processing (e.g. start the network loop). No-op by default."""

    def stop(self) -> None:
        """Stop processing and release resources. No-op by default."""

    # --- typed convenience -------------------------------------------------
    def publish_message(self, message: "Message") -> None:
        """Publish a dataclass message on its own ``TOPIC``."""
        self.publish(message.TOPIC, message.encode())

    def subscribe_message(self, topic: str, handler: "Callable[[Message], None]") -> None:
        """Subscribe with a handler that receives the *decoded* Message."""
        from ..models import decode  # lazy: keep transport independent of schemas

        self.subscribe(topic, lambda _topic, payload: handler(decode(payload)))

    # --- context manager sugar --------------------------------------------
    def __enter__(self) -> "MessageBus":
        self.start()
        return self

    def __exit__(self, *exc) -> bool:
        self.stop()
        return False
