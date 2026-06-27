# Architecture

Intelligent Supermarket Parking System (Group 04) - logical module map and how the
code is organized. See `docs/parking concept model.md` for the physical concept
drawing and the project proposal PDF for the full description.

## Two physical nodes, one communication layer

The system runs as **independent processes** distributed over two machines, glued
together by a publish/subscribe message bus (MQTT - Mosquitto broker, `paho-mqtt`
client). Modules never call each other directly; they exchange events and commands
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

Topic names live in `parking/common/` as the single source of truth. Sensors publish
events; the problem generator and visualization subscribe; the planner publishes plans;
the dispatcher subscribes to plans and publishes actuator commands. Broker config and
run scripts live in `deploy/`.

## Dependencies

Split per node under `requirements/` so each machine installs only what it needs
(`common.txt` is shared; `pi.txt` and `laptop.txt` extend it).
