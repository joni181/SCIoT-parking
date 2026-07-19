"""Topic catalog - the single source of truth for bus topic names.

Modules never hard-code topic strings; they import these constants so the Pi
and the laptop always agree on where messages go. Topics are grouped by
direction of flow:

  events/...    facts observed by sensors (occupancy, motion, NFC, dial)
  commands/...  instructions for actuators (gate, buffer LED, vehicle moves)
  planning/...  AI-planner input/output (problem in, plan out)

The matching `dataclass` for every topic lives in `parking.common.models`.
See docs/message-flow.md for the end-to-end flow and per-topic schemas.
"""
from __future__ import annotations

ROOT = "parking"

# --- Events: published by sensors (Pi); consumed by storage / viz / control ---
EVT_OCCUPANCY = f"{ROOT}/events/occupancy"          # a parking/buffer spot changed state
EVT_GATE_MOTION = f"{ROOT}/events/gate_motion"      # vehicle present/absent at the gate
EVT_NFC_SCAN = f"{ROOT}/events/nfc_scan"            # a card was read (gate or checkout)
EVT_DURATION_DIAL = f"{ROOT}/events/duration_dial"  # rotary dial: expected parking duration
EVT_DISTANCE = f"{ROOT}/events/distance"            # ultrasonic ranger: distance reading

# --- Commands: published by control logic; consumed by actuators (Pi) ---
CMD_GATE = f"{ROOT}/commands/gate"                  # open / close the gate
CMD_BUFFER_LED = f"{ROOT}/commands/buffer_led"      # buffer-slot indicator LED on / off
CMD_LOT_FULL = f"{ROOT}/commands/lot_full"          # status LED: every parking spot occupied
CMD_VEHICLE_MOVE = f"{ROOT}/commands/vehicle_move"  # move a car between buffer <-> spot
CMD_PARKING_ASSIGNMENT = f"{ROOT}/commands/parking_assignment"
CMD_SPOT_DISPLAY = f"{ROOT}/commands/spot_display"
CMD_EXIT_AUTHORIZATION = f"{ROOT}/commands/exit_authorization"

# --- Planning: laptop-internal (problem in, plan out) ---
PLANNING_PROBLEM = f"{ROOT}/planning/problem"       # generated PDDL problem
PLANNING_PLAN = f"{ROOT}/planning/plan"             # solved plan for the dispatcher
PLANNING_ADMISSION = f"{ROOT}/planning/admission"   # accepted/rejected arrival request

# Wildcards, handy for subscribers that want a whole group (e.g. visualization).
ALL_EVENTS = f"{ROOT}/events/#"
ALL_COMMANDS = f"{ROOT}/commands/#"
ALL = f"{ROOT}/#"


def topic_matches(pattern: str, topic: str) -> bool:
    """Return True if an MQTT-style ``pattern`` matches a concrete ``topic``.

    Supports the two MQTT wildcards so the in-memory bus behaves like the real
    broker: ``+`` matches exactly one level, ``#`` matches the rest.

        topic_matches("parking/events/#", "parking/events/occupancy")  -> True
        topic_matches("parking/+/occupancy", "parking/events/occupancy") -> True
    """
    pp = pattern.split("/")
    tp = topic.split("/")
    for i, part in enumerate(pp):
        if part == "#":
            return True
        if i >= len(tp):
            return False
        if part == "+":
            continue
        if part != tp[i]:
            return False
    return len(pp) == len(tp)
