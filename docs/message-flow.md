# Message Flow

How the modules talk to each other. Define this contract once and sensors,
actuators, planner, storage and visualization can be built and tested
independently. See [architecture.md](architecture.md) for the module map.

## Model

Modules never call each other. They publish/subscribe small **messages** on
named **topics** over a shared bus. A publisher doesn't know who listens; a
subscriber doesn't know who sent. That's what keeps modules swappable and lets
us decide what runs where in `apps/`, not in module code.

The bus is an interface (`parking.common.messaging.MessageBus`) with two
transports — same code runs on either:

| Transport | For | Needs |
|---|---|---|
| `MemoryBus` | tests + simulation: in-process, synchronous, deterministic | nothing |
| `MqttBus` | the real distributed system, over a broker | `paho-mqtt` + a running broker |

`MemoryBus` is why we can test the whole flow (and build modules) with **no Pi
and no broker**.

## The broker (how the Pi and laptop share one bus)

The **broker** is a separate server process. Every module — on either machine —
opens a TCP connection to it (`host:1883`) and the broker routes messages by
topic. Nobody connects to anybody directly; everyone connects to the broker.

```
   Pi modules  ──connect──▶ ┌──────────┐  ◀──connect──  laptop modules
   (sensors,                 │  BROKER  │               (storage, planner,
    actuators)               │  :1883   │                visualization)
                             └──────────┘
              published message ──▶ broker ──▶ all subscribers of that topic
```

- **Who starts it:** one machine runs the broker. Per our design that's the
  **laptop** (alongside planner + visualization): `python deploy/broker.py`.
- **How they share it:** the broker binds `0.0.0.0:1883`, so it accepts
  connections from the network. The laptop connects to `localhost`; the Pi
  connects to the laptop's LAN IP via `PARKING_BROKER_HOST` (see below). Both
  are then on the same bus.
- **The broker:** `deploy/broker.py` is a pure-Python broker (`amqtt`) — the
  whole stack stays 100% Python, nothing to install system-wide.

## Topics

Source of truth: [`parking/common/topics.py`](../parking/common/topics.py).
Each topic carries one message type (in
[`parking/common/models/messages.py`](../parking/common/models/messages.py)).

| Topic | Published by | Consumed by | Message |
|---|---|---|---|
| `parking/events/occupancy` | sensors (light) | storage, viz, problem_gen | `OccupancyEvent` |
| `parking/events/gate_motion` | sensors (motion) | control | `GateMotionEvent` |
| `parking/events/nfc_scan` | sensors (NFC) | control, storage | `NfcScanEvent` |
| `parking/events/duration_dial` | sensors (rotary) | storage, problem_gen | `DurationDialEvent` |
| `parking/commands/gate` | control / dispatcher | actuators (gate) | `GateCommand` |
| `parking/commands/buffer_led` | control / dispatcher | actuators (LED) | `BufferLedCommand` |
| `parking/commands/vehicle_move` | dispatcher | actuators (vehicle) | `VehicleMoveCommand` |
| `parking/planning/problem` | problem_generation | planner | `ProblemMessage` |
| `parking/planning/plan` | planner | dispatching, viz | `PlanMessage` |

Group wildcards for broad subscribers: `parking/events/#`, `parking/commands/#`,
`parking/#`. IDs (which spot, which reader) live **in the payload**, not the
topic.

## Message format

JSON envelope: `{"type", "ts", "source", "data": {...}}`. `type` selects the
dataclass on decode; `data` holds the fields below. You normally use the typed
helpers and never touch JSON:

```python
bus.subscribe_message(m.OccupancyEvent.TOPIC, lambda msg: print(msg.spot_id))
bus.publish_message(m.OccupancyEvent(spot_id="P1", occupied=True))
```

| Message | `data` fields |
|---|---|
| `OccupancyEvent` | `spot_id`, `occupied`, `raw_value?` |
| `GateMotionEvent` | `present` |
| `NfcScanEvent` | `uid`, `reader` (`gate`/`checkout`) |
| `DurationDialEvent` | `raw_value`, `minutes?` |
| `GateCommand` | `action` (`open`/`close`) |
| `BufferLedCommand` | `slot_id`, `on` |
| `VehicleMoveCommand` | `vehicle_uid`, `from_spot`, `to_spot` |
| `ProblemMessage` | `problem_id`, `pddl` |
| `PlanMessage` | `problem_id`, `actions` (`[{name, args}]`) |

## The two driving scenarios

**1 — a car parks → the laptop sees it.** The Pi light-sensor driver publishes
`OccupancyEvent(spot_id="P1", occupied=True)`; on the laptop, `storage` updates
the map and `visualization` redraws.

**2 — a car at the gate → the gate opens.** Motion sensor publishes
`GateMotionEvent(present=True)`; the gate NFC reader publishes
`NfcScanEvent(reader="gate", uid=...)`. Control opens the gate **only when both
hold** (car present + recognised card) via `GateCommand(action="open")`; the
gate-motor driver acts on it. When motion clears it sends `close`.

Both run as tests (no hardware) in
[`tests/test_scenarios.py`](../tests/test_scenarios.py).

## Run it

Quick in-process check (no broker, no hardware):

```bash
python examples/message_flow_demo.py
pytest -m "not integration"
```

Full startup (broker + both nodes, one or two machines) and where to set the
broker IP/port: see the **[Getting started guide](../README.md)**.

## Open decisions

1. **Gate = reactive vs. planned.** Demo opens the gate with a reactive rule;
   recommendation: keep the gate reactive in `dispatching`, reserve the planner
   for spot assignment / vehicle moves. (Layer supports both.)
2. **IDs in payload** (current) vs. per-spot topics. Current is simpler.
3. **Broker location** — laptop by default; any node works.
4. **QoS 0, nothing retained.** Add retained state snapshots later if viz should
   show correct state immediately on startup.
