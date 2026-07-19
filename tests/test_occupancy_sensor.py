"""OccupancySensor: parsing the Mega's LIGHT lines into OccupancyEvent."""
from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.sensors import OccupancySensor


def _events(bus: MemoryBus) -> list[m.OccupancyEvent]:
    events: list[m.OccupancyEvent] = []
    bus.subscribe_message(m.OccupancyEvent.TOPIC, events.append)
    return events


def test_below_threshold_is_occupied_by_default():
    bus = MemoryBus()
    events = _events(bus)
    sensor = OccupancySensor(bus, "B1", threshold=512)

    sensor._on_line("LIGHT sensor=photoresistor_a15 raw=100")

    assert len(events) == 1
    assert (events[0].spot_id, events[0].occupied, events[0].raw_value) == ("B1", True, 100)


def test_above_threshold_is_free_by_default():
    bus = MemoryBus()
    events = _events(bus)
    sensor = OccupancySensor(bus, "B1", threshold=512)

    sensor._on_line("LIGHT sensor=photoresistor_a15 raw=900")

    assert events[0].occupied is False
    assert events[0].raw_value == 900


def test_direction_can_be_inverted():
    bus = MemoryBus()
    events = _events(bus)
    sensor = OccupancySensor(bus, "B1", threshold=512, occupied_below_threshold=False)

    sensor._on_line("LIGHT sensor=photoresistor_a15 raw=100")

    assert events[0].occupied is False


def test_ignores_unrelated_lines():
    bus = MemoryBus()
    events = _events(bus)
    sensor = OccupancySensor(bus, "B1")

    sensor._on_line("DISTANCE sensor=hc_sr04p_d7_d24 cm=42")
    sensor._on_line("NFC reader=1 uid=DEADBEEF")

    assert events == []


def test_each_spot_only_reacts_to_its_own_sensor_label():
    """All four OccupancySensor instances see every LIGHT line over the
    shared MegaLink; sensor_label is what keeps P1 from reading B1's sensor."""
    bus = MemoryBus()
    events = _events(bus)
    b1 = OccupancySensor(bus, "B1", sensor_label="photoresistor_a15", threshold=500)
    p1 = OccupancySensor(bus, "P1", sensor_label="photoresistor_a12", threshold=500)
    p2 = OccupancySensor(bus, "P2", sensor_label="photoresistor_a13", threshold=500)

    for sensor in (b1, p1, p2):
        sensor._on_line("LIGHT sensor=photoresistor_a12 raw=100")

    assert [(e.spot_id, e.occupied, e.raw_value) for e in events] == [("P1", True, 100)]


def test_different_spots_can_have_different_thresholds():
    bus = MemoryBus()
    events = _events(bus)
    # Same raw reading, different calibration per mounting - opposite verdicts.
    p1 = OccupancySensor(bus, "P1", sensor_label="photoresistor_a12", threshold=200)
    p2 = OccupancySensor(bus, "P2", sensor_label="photoresistor_a13", threshold=800)

    for sensor in (p1, p2):
        sensor._on_line("LIGHT sensor=photoresistor_a12 raw=400")
        sensor._on_line("LIGHT sensor=photoresistor_a13 raw=400")

    assert [(e.spot_id, e.occupied) for e in events] == [("P1", False), ("P2", True)]
