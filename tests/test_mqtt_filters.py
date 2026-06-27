"""Broker subscription coverage - keeps MqttBus from double-delivering messages.

Tests the pure `_covers` helper only, so no paho/broker is needed.
"""
from parking.common.messaging.mqtt_bus import _covers


def test_exact_and_hash_cover():
    assert _covers("parking/#", "parking/events/occupancy")
    assert _covers("parking/#", "parking")  # '#' also covers the parent
    assert _covers("parking/events/#", "parking/events/occupancy")
    assert _covers("parking/events/occupancy", "parking/events/occupancy")
    assert _covers("#", "anything/at/all")


def test_no_false_coverage():
    assert not _covers("parking/events/occupancy", "parking/events/gate_motion")
    assert not _covers("parking/events/#", "parking/commands/gate")
    # a narrow filter never covers a broader one
    assert not _covers("parking/events/occupancy", "parking/#")
