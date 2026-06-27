# SCIoT Parking — Intelligent Supermarket Parking System

> Drop your car at the entrance, go shopping, and find it waiting for you when you've paid.

An IoT + AI-planning system that **parks and retrieves customer cars automatically** to
minimize walking distance and use parking space efficiently. *(SCIoT practical, Group 04.)*

A customer leaves their car at a **buffer spot** at the entrance, sets an expected parking
duration on a dial, and taps an NFC card. The system parks the car in an assigned spot; once
the customer pays at the register, the car is automatically retrieved back to the buffer for
pickup.

## How it fits together

Two machines, one message bus:

- **Raspberry Pi** — the hardware: sensors (NFC, light, motion, dial) and actuators (gate motor, LED).
- **Laptop** — the brains and the screens: AI planner, data storage, visualization.
- **MQTT broker** — the "post office" both machines dial into; nothing talks directly.

→ Full module map and data flow: **[Architecture](docs/architecture.md)**

## Project map

| Where | What you'll find |
|---|---|
| **[`parking/`](parking/README.md)** | All application code — one folder per logical module |
| ↳ [`parking/common/`](parking/common/README.md) | The communication layer (MQTT), shared by both nodes |
| **[`apps/`](apps/README.md)** | Entrypoints you actually run: `pi_node` · `laptop_node` · `planner` |
| **[`config/`](config/README.md)** | Per-node runtime settings (broker address, parking layout) |
| **[`deploy/`](deploy/README.md)** | MQTT broker config + run scripts |
| **[`requirements/`](requirements/)** | Per-node Python dependencies (`common` ← `pi` / `laptop`) |
| **[`docs/`](docs/architecture.md)** | [Architecture](docs/architecture.md) · [Concept drawing](docs/parking%20concept%20model.md) |
| **[`experiments/`](experiments/)** | Hardware spikes / sensor test scripts (reference) |

## Getting started

_Coming soon — broker bring-up and launching the two nodes._
