"""paho-mqtt backed bus - the real transport for the distributed system.

This is the only place that knows about MQTT. ``paho`` is imported lazily inside
``__init__`` so that importing the package (and running the MemoryBus-based
tests) needs no MQTT install at all.

Needs a running broker; see deploy/broker.py (pure-Python, amqtt).

Subscriptions are fanned out *locally*: each incoming message is dispatched to
every handler whose topic filter matches. To avoid the broker delivering the
same message more than once, we only subscribe a **minimal, non-overlapping**
set of filters at the broker (e.g. if something subscribes ``parking/#`` we
don't also subscribe ``parking/events/occupancy`` to the broker - it's already
covered, and we still dispatch to both handlers ourselves).
"""
from __future__ import annotations

from typing import List, Set, Tuple

from ..topics import topic_matches
from .bus import Handler, MessageBus


def _covers(broad: str, narrow: str) -> bool:
    """True if subscribing to ``broad`` already delivers everything ``narrow`` would.

    Handles exact equality and the ``#`` (multi-level) wildcard, which is what
    overlapping subscriptions look like in practice.
    """
    if broad == narrow:
        return True
    if broad == "#":
        return True
    if broad.endswith("/#"):
        prefix = broad[:-1]            # "parking/#" -> "parking/"
        parent = broad[:-2]            # "parking/#" -> "parking"
        return narrow == parent or narrow.startswith(prefix)
    return False


class MqttBus(MessageBus):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        client_id: str | None = None,
        keepalive: int = 60,
    ) -> None:
        import paho.mqtt.client as mqtt  # lazy: only needed on real nodes

        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._subs: List[Tuple[str, Handler]] = []   # all local handlers
        self._broker_filters: Set[str] = set()        # what we told the broker

        # paho 2.x requires the callback-API version; fall back for 1.x.
        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        except (AttributeError, TypeError):
            self._client = mqtt.Client(client_id=client_id)

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    # --- paho callbacks ----------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        # (Re)subscribe the minimal covering set on every (re)connect, so we
        # recover from broker restarts.
        self._broker_filters.clear()
        for topic in self._minimal_filters():
            self._broker_filters.add(topic)
            client.subscribe(topic)

    def _on_message(self, client, userdata, msg) -> None:
        for pattern, handler in list(self._subs):
            if topic_matches(pattern, msg.topic):
                handler(msg.topic, msg.payload)

    # --- subscription bookkeeping -----------------------------------------
    def _minimal_filters(self) -> Set[str]:
        wanted = {topic for topic, _ in self._subs}
        return {f for f in wanted if not any(o != f and _covers(o, f) for o in wanted)}

    def _ensure_broker_subscribed(self, topic: str) -> None:
        if any(_covers(existing, topic) for existing in self._broker_filters):
            return  # already covered by a broader/equal subscription
        # Drop any existing broker filters this new one makes redundant.
        for existing in {e for e in self._broker_filters if _covers(topic, e)}:
            self._client.unsubscribe(existing)
            self._broker_filters.discard(existing)
        self._broker_filters.add(topic)
        self._client.subscribe(topic)

    # --- MessageBus API ----------------------------------------------------
    def publish(self, topic: str, payload: bytes | str) -> None:
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        self._client.publish(topic, payload)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs.append((topic, handler))
        if self._client.is_connected():
            self._ensure_broker_subscribed(topic)

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def start(self) -> None:
        self._client.connect(self._host, self._port, self._keepalive)
        self._client.loop_start()  # background network thread

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
