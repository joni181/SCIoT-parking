# Architecture

Intelligent Supermarket Parking System (Group 04) - logical module map and how the
code is organized. See `docs/parking concept model.md` for the physical concept
drawing and the project proposal PDF for the full description.

## Two physical nodes, one communication layer

The system runs as **independent processes** distributed over two machines, glued
together by a publish/subscribe message bus (MQTT - pure-Python `amqtt` broker +
`paho-mqtt` client). Modules never call each other directly; they exchange events and commands
over named topics. This keeps the design deployment-independent: *which* process runs
*where* is decided by the launch entrypoints in `apps/`, not by the module code.

- **Raspberry Pi node** (`apps/pi_node.py`): all hardware I/O - sensors, actuators, dispatching.
- **Laptop node** (`apps/laptop_node.py`): compute + UI - problem generation, planner, storage, visualization.
- The **AI planner** is deployment-agnostic and may run on either node.

## Modules (`parking/`)

| Folder | Responsibility | Runs on |
|---|---|---|
| `common/` | Communication layer + shared contracts: MQTT client wrapper, topic catalog, message schemas, config. Used identically by both nodes. | both |
| `sensors/` | Drivers for NFC reader, light, motion, rotary sensors. Publish raw events. | Pi |
| `actuators/` | Drivers for gate stepper motor, buffer LED, (simulated) vehicle motion. | Pi |
| `dispatching/` | Consume planner output; command actuators to execute the plan. | Pi |
| `storage/` | Vehicle-to-spot mapping and customer DB (customer-vehicle, estimated duration). | laptop |
| `problem_generation/` | Translate current occupancy + customer state into a PDDL problem. | laptop |
| `planning/` | PDDL domain (`domain/`) + forward-search classical planner. | either |
| `visualization/` | Parking-lot state display + plan-execution display (Python). | laptop |

## Communication

Topic names live in `parking/common/topics.py` as the single source of truth, and the
message schemas in `parking/common/models/`. Sensors publish events; the problem
generator and visualization subscribe; the planner publishes plans; the dispatcher
subscribes to plans and publishes actuator commands. Broker config and run scripts live
in `deploy/`.

The bus (`parking/common/messaging/`) has two transports: `MqttBus` (real run) and
`MemoryBus` (in-process, for testing the whole flow with no broker/hardware via the
simulated devices in `parking/simulation/`). The broker runs as a separate process
(`deploy/broker.py`, pure-Python `amqtt`).

See **[message-flow.md](message-flow.md)** for the topic catalog, message formats, the
broker, and the two end-to-end scenarios. Try `python examples/message_flow_demo.py`.

## Interfaces (two layers)

There are two distinct contracts in the system, and it helps to keep them apart:

1. **Between modules — the wire contract.** Modules never import each other; they
   only exchange messages. So the *inter-module* interface is the pair
   **topics + message schemas** in `common/` (above). A sensor depends on
   `OccupancyEvent`, not on `storage`.
2. **Inside each module — the code port.** Each module folder declares its own role
   as a small `typing.Protocol` in a `base.py`, so a concrete implementation can be
   swapped (real hardware ↔ simulation, in-memory store ↔ DB, one planner ↔ another)
   without touching anyone else. These are structural `@runtime_checkable` Protocols;
   `tests/test_interfaces.py` enforces that every implementation satisfies its port.

All bus-attached parts share one tiny lifecycle interface,
`parking.common.Component` (`start()` / `stop()`), so an entrypoint in `apps/` can
wire and run a mixed bag of them uniformly.

| Module | Port (`base.py`) | Shipped implementation | Stand-in (simulation) |
|---|---|---|---|
| `sensors/` | `Sensor` (a `Component`) | `OccupancySensor`, `GateMotionSensor`, `NfcReader`, `DurationDial` *(skeletons)* | `SimulatedSensors` |
| `actuators/` | `Actuator` (a `Component`) | `GateMotor`, `BufferLed`, `VehicleMover` *(skeletons)* | `RecordingActuators` |
| `dispatching/` | `Dispatcher` (a `Component`) | `PlanDispatcher` *(skeleton)* | `ReactiveGateController` |
| `storage/` | `OccupancyStore` / `CustomerStore` / `StateStore` | `InMemoryStore` | `OccupancyTracker` *(implements `OccupancyStore`)* |
| `problem_generation/` | `ProblemGenerator` | `PddlProblemGenerator` *(skeleton)* | — |
| `planning/` | `Planner` | `ForwardSearchPlanner` *(skeleton)* + `domain/domain.pddl` | — |
| `visualization/` | `View` (a `Component`) | `ConsoleLotView` *(skeleton)* | `OccupancyTracker` doubles as viz |

*Skeletons* carry the real interface and `TODO`s where the hardware/algorithm drops
in — so teammates can build a module against its port today and the message flow keeps
running.

## Dependencies

Split per node under `requirements/` so each machine installs only what it needs
(`common.txt` is shared; `pi.txt` and `laptop.txt` extend it).
