"""DurationDial: mapping the Mega's ROTARY ticks lines to a duration."""
from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.sensors import DurationDial


def _events(bus: MemoryBus) -> list[m.DurationDialEvent]:
    events: list[m.DurationDialEvent] = []
    bus.subscribe_message(m.DurationDialEvent.TOPIC, events.append)
    return events


def test_zero_ticks_is_the_default_minutes():
    bus = MemoryBus()
    events = _events(bus)
    dial = DurationDial(bus, default_minutes=30, minutes_per_tick=5)

    dial._on_line("ROTARY ticks=0")

    assert (events[0].raw_value, events[0].minutes) == (0, 30)


def test_positive_and_negative_ticks_shift_minutes():
    bus = MemoryBus()
    events = _events(bus)
    dial = DurationDial(bus, default_minutes=30, minutes_per_tick=5)

    dial._on_line("ROTARY ticks=4")
    dial._on_line("ROTARY ticks=-2")

    assert [e.minutes for e in events] == [50, 20]


def test_minutes_are_clamped_to_the_configured_range():
    bus = MemoryBus()
    events = _events(bus)
    dial = DurationDial(bus, default_minutes=30, minutes_per_tick=5, min_minutes=5, max_minutes=60)

    dial._on_line("ROTARY ticks=-100")
    dial._on_line("ROTARY ticks=100")

    assert [e.minutes for e in events] == [5, 60]


def test_ignores_unrelated_lines():
    bus = MemoryBus()
    events = _events(bus)
    dial = DurationDial(bus)

    dial._on_line("LIGHT sensor=photoresistor_a15 raw=500")
    dial._on_line("GATE state=open angle=180 pulse_us=2000")

    assert events == []
