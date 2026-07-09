# simulation  [tests + demo, both nodes]

Hardware-free stand-ins that exercise the message flow before the Raspberry Pi and the
Grove/RC522 hardware are wired up. Pair them with
[`MemoryBus`](../common/messaging/memory_bus.py) for deterministic, broker-free runs
(see [`tests/`](../../tests/README.md) and `examples/message_flow_demo.py`).

The component-shaped stand-ins speak the corresponding real module interfaces.
`SimulatedSensors` is a multi-sensor scenario helper rather than one `Sensor`:

| Stand-in | Role | Port it fulfils |
|---|---|---|
| `SimulatedSensors` | injects sensor events on demand | counterpart of [`sensors`](../sensors/README.md) drivers (manual injector, not a single `Sensor`) |
| `RecordingActuators` | records actuator commands | [`Actuator`](../actuators/base.py) test double for the hardware drivers |
| `ReactiveGateController` | open/close gate on motion + known card | [`Component`](../common/component.py); foreshadows [`dispatching`](../dispatching/README.md) |
| `OccupancyTracker` | track spot occupancy from events | [`OccupancyStore`](../storage/base.py); stands in for [`storage`](../storage/README.md) + [`visualization`](../visualization/README.md) |

`GuidedScenarioController` and `MqttDemoSystem` power the standalone laptop
dashboard example. Unlike the small `MemoryBus` walkthrough, they use two real
MQTT clients and wait for actual planner/dispatcher commands before confirming
simulated physical movement. Start/advance/reset controls are exposed only in the
demo dashboard, never in the production laptop view. Scenarios wait at every
human/sensor boundary until **Advance simulation** is pressed.
