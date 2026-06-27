"""The in-memory bus: pub/sub, wildcards, and the typed convenience helpers."""
from parking.common import models as m
from parking.common import topics
from parking.common.messaging import MemoryBus


def test_publish_reaches_exact_subscriber():
    bus = MemoryBus()
    received = []
    bus.subscribe(topics.EVT_OCCUPANCY, lambda t, p: received.append((t, p)))

    bus.publish(topics.EVT_OCCUPANCY, b"hello")
    assert received == [(topics.EVT_OCCUPANCY, b"hello")]


def test_string_payload_is_encoded_to_bytes():
    bus = MemoryBus()
    received = []
    bus.subscribe(topics.EVT_OCCUPANCY, lambda t, p: received.append(p))
    bus.publish(topics.EVT_OCCUPANCY, "hi")
    assert received == [b"hi"]


def test_wildcard_subscriber_gets_group():
    bus = MemoryBus()
    seen = []
    bus.subscribe(topics.ALL_EVENTS, lambda t, p: seen.append(t))

    bus.publish(topics.EVT_OCCUPANCY, b"x")
    bus.publish(topics.EVT_GATE_MOTION, b"y")
    bus.publish(topics.CMD_GATE, b"z")  # a command, not an event

    assert seen == [topics.EVT_OCCUPANCY, topics.EVT_GATE_MOTION]


def test_no_subscriber_is_not_an_error():
    bus = MemoryBus()
    bus.publish(topics.CMD_GATE, b"nobody listening")
    assert bus.published == [(topics.CMD_GATE, b"nobody listening")]


def test_typed_publish_and_subscribe():
    bus = MemoryBus()
    got = []
    bus.subscribe_message(topics.EVT_OCCUPANCY, got.append)

    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))

    assert len(got) == 1
    assert isinstance(got[0], m.OccupancyEvent)
    assert got[0].spot_id == "P1" and got[0].occupied is True
