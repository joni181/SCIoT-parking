# simulation  [tests + demo, both nodes]

Hardware-free stand-ins that exercise the message flow before the Raspberry Pi and the
Grove/RC522 hardware are wired up. Pair them with
[`MemoryBus`](../common/messaging/memory_bus.py) for deterministic, broker-free runs
(see [`tests/`](../../tests/README.md) and `examples/message_flow_demo.py`).

Each stand-in already speaks the real module interface, so the production module is a
drop-in replacement:

| Stand-in | Role | Port it fulfils |
|---|---|---|
| `SimulatedSensors` | injects sensor events on demand | counterpart of [`sensors`](../sensors/README.md) drivers (manual injector, not a single `Sensor`) |
| `RecordingActuators` | records actuator commands | test double for [`actuators`](../actuators/README.md) drivers |
| `ReactiveGateController` | open/close gate on motion + known card | [`Component`](../common/component.py); foreshadows [`dispatching`](../dispatching/README.md) |
| `OccupancyTracker` | track spot occupancy from events | [`OccupancyStore`](../storage/base.py); stands in for [`storage`](../storage/README.md) + [`visualization`](../visualization/README.md) |
