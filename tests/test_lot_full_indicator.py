"""LotFullIndicator: publishing LotFullCommand only when the all-occupied
state of the configured parking spots actually changes."""
from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.dispatching import LotFullIndicator


def _commands(bus: MemoryBus) -> list[m.LotFullCommand]:
    commands: list[m.LotFullCommand] = []
    bus.subscribe_message(m.LotFullCommand.TOPIC, commands.append)
    return commands


def test_not_full_until_every_configured_spot_is_occupied():
    bus = MemoryBus()
    commands = _commands(bus)
    LotFullIndicator(bus, ["P1", "P2", "P3"]).start()

    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))
    bus.publish_message(m.OccupancyEvent(spot_id="P2", occupied=True))

    assert [c.full for c in commands] == [False]  # first known state only


def test_publishes_full_true_once_the_last_spot_fills():
    bus = MemoryBus()
    commands = _commands(bus)
    LotFullIndicator(bus, ["P1", "P2", "P3"]).start()

    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))
    bus.publish_message(m.OccupancyEvent(spot_id="P2", occupied=True))
    bus.publish_message(m.OccupancyEvent(spot_id="P3", occupied=True))

    assert [c.full for c in commands] == [False, True]


def test_does_not_republish_when_full_state_is_unchanged():
    bus = MemoryBus()
    commands = _commands(bus)
    LotFullIndicator(bus, ["P1", "P2", "P3"]).start()

    for spot in ("P1", "P2", "P3"):
        bus.publish_message(m.OccupancyEvent(spot_id=spot, occupied=True))
    # Redundant re-reports of an already-occupied spot shouldn't republish.
    bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))

    assert [c.full for c in commands] == [False, True]


def test_publishes_full_false_when_a_spot_frees_up():
    bus = MemoryBus()
    commands = _commands(bus)
    LotFullIndicator(bus, ["P1", "P2", "P3"]).start()

    for spot in ("P1", "P2", "P3"):
        bus.publish_message(m.OccupancyEvent(spot_id=spot, occupied=True))
    bus.publish_message(m.OccupancyEvent(spot_id="P2", occupied=False))

    assert [c.full for c in commands] == [False, True, False]


def test_ignores_spots_outside_the_configured_list():
    bus = MemoryBus()
    commands = _commands(bus)
    LotFullIndicator(bus, ["P1", "P2", "P3"]).start()

    bus.publish_message(m.OccupancyEvent(spot_id="B1", occupied=True))

    assert commands == []
