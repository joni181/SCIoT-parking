# Architecture

Intelligent Supermarket Parking System (Group 04) - logical module map and how the
code is organized. See `docs/parking concept model.md` for the physical concept
drawing and the project proposal PDF for the full description.

## Two physical nodes, one communication layer

The system runs as **independent processes** distributed over two machines, glued
together by a publish/subscribe message bus (MQTT - pure-Python `amqtt` broker +
`paho-mqtt` client). Runtime events and commands never cross process boundaries through
direct calls; they use named topics. Within one process, composition roots may inject a
narrow protocol such as `StateStore` into a pure service such as `ProblemGenerator`.
This keeps deployment decisions in the launch entrypoints under `apps/`.

- **Raspberry Pi node** (`apps/pi_node.py`): actuator and sensor skeletons plus reactive
  gate control; simulated sensors are the default until hardware drivers are implemented.
- **Laptop node** (`apps/laptop_node.py`): storage + local Dash operator dashboard.
- The **AI planner** is deployment-agnostic. It runs in `apps/laptop_node.py` by
  default, or as `apps/planner.py` when deployed separately.

## Modules (`parking/`)

| Folder | Responsibility | Runs on |
|---|---|---|
| `common/` | Communication layer + shared contracts: MQTT client wrapper, topic catalog, message schemas, config. Used identically by both nodes. | both |
| `sensors/` | Drivers for NFC reader, light, motion, rotary sensors. Publish raw events. | Pi |
| `actuators/` | Drivers for gate servo, spot/buffer LED, and simulated vehicle motion. | Pi |
| `dispatching/` | Consume planner output; command actuators to execute the plan. | Pi |
| `storage/` | Vehicle-to-spot mapping and customer DB (customer-vehicle, estimated duration). | laptop |
| `problem_generation/` | Translate current occupancy + customer state into a PDDL problem. | laptop |
| `planning/` | PDDL domain (`domain/`) + forward-search classical planner. | either |
| `visualization/` | Operator dashboard: current instruction, parking-lot/gate state, assignments, and diagnostics. | laptop |

## Communication

Topic names live in `parking/common/topics.py` as the single source of truth, and the
message schemas in `parking/common/models/`. Sensors publish events; storage and
visualization subscribe; a planner service consumes generated problems and publishes
plans; the dispatcher consumes plans and publishes actuator commands. Problem
generation reads `StateStore` after occupancy, NFC, dial, and vehicle-move events.
Broker config and run scripts live in `deploy/`.

The bus (`parking/common/messaging/`) has two transports: `MqttBus` (real run) and
`MemoryBus` (in-process, for testing the whole flow with no broker/hardware via the
simulated devices in `parking/simulation/`). The broker runs as a separate process
(`deploy/broker.py`, pure-Python `amqtt`).

See **[message-flow.md](message-flow.md)** for the topic catalog, message formats, the
broker, and the two end-to-end scenarios. Try `python examples/message_flow_demo.py`.

## Interfaces (two layers)

There are two distinct contracts in the system, and it helps to keep them apart:

1. **Across processes and for runtime signals — the wire contract.** Components
   exchange events and commands through **topics + message schemas** in `common/`.
   A sensor publishes `OccupancyEvent`; it does not call `storage`.
2. **For in-process composition — the code port.** Each module folder declares its
   role as a small `typing.Protocol` in a `base.py`, so a concrete implementation can be
   swapped (real hardware ↔ simulation, in-memory store ↔ DB, one planner ↔ another)
   without changing its consumers. A composition root may pass one of these ports to a
   service in the same process. These are structural `@runtime_checkable` Protocols;
   `tests/test_interfaces.py` enforces that implementations satisfy their ports.

All bus-attached parts share one tiny lifecycle interface,
`parking.common.Component` (`start()` / `stop()`), so an entrypoint in `apps/` can
wire and run a mixed bag of them uniformly.

| Module | Port (`base.py`) | Shipped implementation | Stand-in (simulation) |
|---|---|---|---|
| `sensors/` | `Sensor` (a `Component`) | `OccupancySensor`, `NfcReader`, `DurationDial` *(skeletons)*, `DistanceSensor` *(live)* | `SimulatedSensors` *(multi-sensor helper, not one `Sensor`)* |
| `actuators/` | `Actuator` (a `Component`) | `GateMotor`, `BufferLed`, `VehicleMover` *(skeletons)*; `GateServo` is live | `RecordingActuators` |
| `dispatching/` | `Dispatcher` (a `Component`) | `PlanDispatcher`; `GateSafetyController` closes the gate on a timer (no motion sensor exists); `LotFullIndicator` drives the status LED | `ReactiveGateController` |
| `storage/` | `OccupancyStore` / `CustomerStore` / `StateStore` | `InMemoryStore` | `OccupancyTracker` *(implements `OccupancyStore`)* |
| `problem_generation/` | `ProblemGenerator` | `PddlProblemGenerator` + bus service | — |
| `planning/` | `Planner` | `ForwardSearchPlanner` + bus service + `domain/domain.pddl` | — |
| `visualization/` | `View` (a `Component`) | `DashboardView` + thread-safe `DashboardModel`; `ConsoleLotView` fallback | `OccupancyTracker` doubles as viz |

*Skeletons* carry the real interface and `TODO`s where the hardware/algorithm drops
in — so teammates can build a module against its port today and the message flow keeps
running.

The dashboard uses the laptop's shared `StateStore` for lifecycle/assignment
snapshots and observes `parking/#` for transient gate, plan, admission and
activity state. Gate state is shown inside the physical lot map; plans and raw
activity are diagnostics, not the main operator workflow. MQTT callbacks only
update a locked immutable projection; the browser polls that projection every
500 ms. The production view never publishes control messages.

## Dependencies

Split per node under `requirements/` so each machine installs only what it needs
(`common.txt` is shared; `pi.txt` and `laptop.txt` extend it).
