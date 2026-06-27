# tests

Three tiers, fast to most-realistic. All run with plain `pytest`.

| Tier | Files | What it exercises | Speed / needs |
|---|---|---|---|
| **Unit + scenario** | `tests/test_*.py` | message schemas, the bus, topic matching, and both driving scenarios — all on the in-process `MemoryBus` | instant, stdlib only |
| **Live transport** | `tests/integration/test_live_mqtt.py` | the same scenarios over a **real broker** with two real `MqttBus` (paho) clients — JSON on the wire, the network, connection setup, subscription de-dup | needs `amqtt` + `paho-mqtt` |
| **Real processes** | `tests/integration/test_node_processes.py` | launches the actual `deploy/broker.py` + `apps/pi_node.py` + `apps/laptop_node.py` as **three separate OS processes** on a free port — the closest mirror of the laptop+Pi deployment | needs `amqtt` + `paho-mqtt`, slower |

The integration tier auto-skips if `amqtt`/`paho-mqtt` aren't installed, so the
core suite always runs with zero dependencies.

```bash
pytest                       # everything (skips integration if deps missing)
pytest -m "not integration"  # only the fast unit/scenario tier
pytest tests/integration     # only the broker-backed tiers
```

The integration broker is the *same* pure-Python `amqtt` server the laptop runs
(`deploy/broker.py`), so these tests connect exactly like the live nodes do.
Hardware drivers, when added, should likewise be tested against the bus (real or
in-memory), never by requiring the physical Pi.
