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
| **[`deploy/`](deploy/README.md)** | The MQTT broker — a pure-Python `amqtt` server (`broker.py`) |
| **[`requirements/`](requirements/)** | Per-node Python dependencies (`common` ← `pi` / `laptop`) |
| **[`docs/`](docs/architecture.md)** | [Architecture](docs/architecture.md) · [Message flow](docs/message-flow.md) · [Concept drawing](docs/parking%20concept%20model.md) |
| **[`experiments/`](experiments/)** | Hardware spikes / sensor test scripts (reference) |

## Getting started

The broker is **one process on the laptop**; every node dials into it. The whole
stack is Python — nothing to install system-wide.

### 0. Install dependencies

```bash
pip install -r requirements/laptop.txt   # on the laptop (broker + compute)
pip install -r requirements/pi.txt       # on the Raspberry Pi
pip install -r requirements/dev.txt      # for development / running the tests
```

### 1. Set the broker address (once per machine)

```bash
cp config/config.example.yaml config/config.yaml
```

Edit `config/config.yaml`:
- **Laptop:** leave `broker_host: 127.0.0.1`.
- **Pi:** set `broker_host` to the laptop's **LAN IP** (e.g. `192.168.0.10`) and
  `node_name: pi`. Both machines must be on the same network.

`config/config.yaml` is git-ignored, so each machine keeps its own. (One-off
override without editing the file: `PARKING_BROKER_HOST=… PARKING_BROKER_PORT=…`.)

### 2. Start everything

**Laptop** (two terminals):

```bash
python deploy/broker.py        # 1) the MQTT broker — keep it running
python apps/laptop_node.py     # 2) the laptop side — watches the bus
```

**Pi** (or a third laptop terminal for a no-hardware dry run):

```bash
python apps/pi_node.py         # connects to the broker and plays a scenario
```

The Pi's events show up in `laptop_node`, and the gate command comes back — the
full round trip across the network.

### Try it without hardware or a broker

```bash
python examples/message_flow_demo.py   # both scenarios, one process
pytest -m "not integration"            # fast tests, no broker (in-memory bus)
```

(Bare `pytest` also runs the broker-backed integration tier — see [tests/README.md](tests/README.md).)
