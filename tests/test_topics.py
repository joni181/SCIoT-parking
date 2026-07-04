"""Topic wildcard matching - the in-memory bus relies on this behaving like MQTT."""
from parking.common import topics


def test_exact_match():
    assert topics.topic_matches("parking/events/occupancy", "parking/events/occupancy")
    assert not topics.topic_matches("parking/events/occupancy", "parking/events/gate_motion")


def test_plus_matches_single_level():
    assert topics.topic_matches("parking/+/occupancy", "parking/events/occupancy")
    assert not topics.topic_matches("parking/+/occupancy", "parking/events/sub/occupancy")
    # '+' needs exactly one level present
    assert not topics.topic_matches("parking/events/+", "parking/events")


def test_hash_matches_rest():
    assert topics.topic_matches("parking/#", "parking/events/occupancy")
    assert topics.topic_matches("parking/events/#", "parking/events/occupancy")
    assert topics.topic_matches("parking/#", "parking")  # '#' also matches the parent


def test_group_wildcards_cover_their_topics():
    assert topics.topic_matches(topics.ALL_EVENTS, topics.EVT_OCCUPANCY)
    assert topics.topic_matches(topics.ALL_COMMANDS, topics.CMD_GATE)
    assert topics.topic_matches(topics.ALL, topics.PLANNING_PLAN)
    assert not topics.topic_matches(topics.ALL_EVENTS, topics.CMD_GATE)
