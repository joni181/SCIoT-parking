"""Pure-Python MQTT broker (amqtt) - the development broker.

Run this on the machine that hosts the broker (per the design: the laptop).
Every module on every node then connects to it through `MqttBus`. No system
install needed - it's just Python.

    python deploy/broker.py                      # binds 0.0.0.0:1883
    PARKING_BROKER_PORT=1884 python deploy/broker.py

Binds 0.0.0.0 so the Raspberry Pi can reach it across the network.
"""
from __future__ import annotations

import asyncio
import os

from amqtt.broker import Broker

BIND_HOST = os.environ.get("PARKING_BROKER_BIND", "0.0.0.0")
PORT = int(os.environ.get("PARKING_BROKER_PORT", "1883"))

CONFIG = {
    "listeners": {"default": {"type": "tcp", "bind": f"{BIND_HOST}:{PORT}"}},
    "sys_interval": 0,
    "auth": {"allow-anonymous": True},  # fine for a closed lab/demo network
}


async def main() -> None:
    broker = Broker(CONFIG)  # constructed inside the running loop (required)
    await broker.start()
    print(f"[broker] amqtt listening on {BIND_HOST}:{PORT} (anonymous). Ctrl-C to stop.")
    try:
        await asyncio.Event().wait()  # run until cancelled
    finally:
        await broker.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[broker] stopped.")
